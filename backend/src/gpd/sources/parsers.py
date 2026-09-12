from dataclasses import dataclass
import hashlib
import re
import unicodedata

MAX_SOURCE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MiB


class SourceValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedChunk:
    locator: str
    text: str
    token_estimate: int


@dataclass(frozen=True)
class HeadingSection:
    locator: str
    text: str


def validate_and_normalize_content(raw_content: str) -> str:
    """Normalize UTF-8, reject NUL bytes, and enforce 2 MiB size cap."""
    if "\x00" in raw_content:
        raise SourceValidationError("null_byte_detected", "Source content contains NUL bytes")

    encoded = raw_content.encode("utf-8")
    if len(encoded) > MAX_SOURCE_SIZE_BYTES:
        raise SourceValidationError(
            "content_too_large",
            f"Source content ({len(encoded)} bytes) exceeds the 2 MiB limit",
        )

    # Unicode NFC normalization
    return unicodedata.normalize("NFC", raw_content)


def compute_content_hash(normalized_content: str) -> str:
    """Compute SHA-256 digest of normalized content."""
    return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()


def split_on_markdown_headings(content: str) -> list[HeadingSection]:
    """Split markdown text into sections by ATX headings (# to ######)."""
    lines = content.splitlines(keepends=True)
    sections: list[HeadingSection] = []

    current_locator = "preamble"
    current_lines: list[str] = []

    heading_regex = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in lines:
        match = heading_regex.match(line.strip())
        if match:
            if current_lines:
                text = "".join(current_lines).strip()
                if text:
                    sections.append(HeadingSection(locator=current_locator, text=text))
                current_lines = []
            heading_title = match.group(2).strip()
            slug = re.sub(r"[^\w\s-]", "", heading_title.lower()).strip()
            slug = re.sub(r"[-\s]+", "-", slug)
            current_locator = slug or "section"
            current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        text = "".join(current_lines).strip()
        if text:
            sections.append(HeadingSection(locator=current_locator, text=text))

    if not sections and content.strip():
        sections.append(HeadingSection(locator="root", text=content.strip()))

    return sections


def split_long_text(text: str, max_chunk_chars: int = 4_000) -> list[str]:
    """Split a section of text into chunks not exceeding max_chunk_chars."""
    if len(text) <= max_chunk_chars:
        return [text] if text.strip() else []

    paragraphs = re.split(r"(\n\s*\n)", text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for part in paragraphs:
        part_len = len(part)
        if current_length + part_len > max_chunk_chars and current_chunk:
            combined = "".join(current_chunk).strip()
            if combined:
                chunks.append(combined)
            current_chunk = []
            current_length = 0

        if part_len > max_chunk_chars:
            lines = part.splitlines(keepends=True)
            for line in lines:
                if current_length + len(line) > max_chunk_chars and current_chunk:
                    combined = "".join(current_chunk).strip()
                    if combined:
                        chunks.append(combined)
                    current_chunk = []
                    current_length = 0

                if len(line) > max_chunk_chars:
                    for i in range(0, len(line), max_chunk_chars):
                        slice_piece = line[i : i + max_chunk_chars].strip()
                        if slice_piece:
                            chunks.append(slice_piece)
                else:
                    current_chunk.append(line)
                    current_length += len(line)
        else:
            current_chunk.append(part)
            current_length += part_len

    if current_chunk:
        combined = "".join(current_chunk).strip()
        if combined:
            chunks.append(combined)

    return chunks


def parse_markdown(content: str, max_chunk_chars: int = 4_000) -> list[ParsedChunk]:
    """Parse markdown content into structured, locator-indexed chunks."""
    headings = split_on_markdown_headings(content)
    result: list[ParsedChunk] = []

    for section in headings:
        pieces = split_long_text(section.text, max_chunk_chars=max_chunk_chars)
        for idx, piece in enumerate(pieces):
            clean_piece = piece.strip()
            if not clean_piece:
                continue
            locator = f"{section.locator}:{idx}" if len(pieces) > 1 else section.locator
            token_estimate = max(1, len(clean_piece) // 4)
            result.append(
                ParsedChunk(
                    locator=locator,
                    text=clean_piece,
                    token_estimate=token_estimate,
                )
            )

    return result
