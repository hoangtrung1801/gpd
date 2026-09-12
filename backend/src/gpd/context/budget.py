from collections.abc import Sequence
from gpd.context.schemas import SECTION_ORDER, CandidateEntry


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def compact_mandatory(mandatory: Sequence[CandidateEntry], limit: int) -> list[CandidateEntry]:
    compacted: list[CandidateEntry] = []
    
    num_entries = len(mandatory) if mandatory else 1
    per_entry_limit = max(10, limit // num_entries)

    for entry in mandatory:
        content = entry.content
        if entry.section == "task":
            # Extract title line if present, else first line
            lines = content.splitlines()
            title_line = ""
            for l in lines:
                if "Title:" in l:
                    title_line = l
                    break
            if not title_line and lines:
                title_line = lines[0]
            shortened = title_line[:per_entry_limit * 4]
            est = estimate_tokens(shortened)
            compacted.append(
                CandidateEntry(
                    section=entry.section,
                    content=shortened,
                    token_estimate=est,
                    is_mandatory=True,
                )
            )
        elif entry.section == "expected_actual":
            # Keep actual & expected lines
            shortened = content[:per_entry_limit * 4]
            est = estimate_tokens(shortened)
            compacted.append(
                CandidateEntry(
                    section=entry.section,
                    content=shortened,
                    token_estimate=est,
                    is_mandatory=True,
                )
            )
        elif entry.section in ("work_warnings", "high_severity_conflicts"):
            # High warnings
            shortened = content[:per_entry_limit * 4]
            est = estimate_tokens(shortened)
            compacted.append(
                CandidateEntry(
                    section=entry.section,
                    content=shortened,
                    token_estimate=est,
                    is_mandatory=True,
                )
            )
        else:
            shortened = content[:max(10, per_entry_limit * 2)]
            est = estimate_tokens(shortened)
            compacted.append(
                CandidateEntry(
                    section=entry.section,
                    content=shortened,
                    token_estimate=est,
                    is_mandatory=True,
                )
            )

    # Ensure total strictly <= limit
    total = sum(c.token_estimate for c in compacted)
    if total > limit and compacted:
        factor = limit / total
        for c in compacted:
            new_len = max(8, int(len(c.content) * factor))
            c.content = c.content[:new_len]
            c.token_estimate = estimate_tokens(c.content)

    return compacted


class TokenBudget:
    def select(
        self,
        mandatory: Sequence[CandidateEntry],
        optional: Sequence[CandidateEntry],
        limit: int,
    ) -> tuple[list[CandidateEntry], list[str]]:
        selected = list(mandatory)
        current_total = sum(item.token_estimate for item in selected)
        
        if current_total > limit:
            compacted = compact_mandatory(mandatory, limit)
            compacted.sort(key=lambda x: SECTION_ORDER.index(x.section) if x.section in SECTION_ORDER else 99)
            return compacted, ["budget_exceeded_by_mandatory"]

        remaining = limit - current_total
        warnings: list[str] = []

        sorted_optional = sorted(
            optional,
            key=lambda x: (x.score if x.score is not None else 0.0),
            reverse=True,
        )

        for item in sorted_optional:
            if item.token_estimate <= remaining:
                selected.append(item)
                remaining -= item.token_estimate

        selected.sort(key=lambda x: SECTION_ORDER.index(x.section) if x.section in SECTION_ORDER else 99)
        return selected, warnings
