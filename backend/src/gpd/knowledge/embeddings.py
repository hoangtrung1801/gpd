import hashlib
import math
from typing import Protocol, Sequence


def validate_embedding(vector: Sequence[float], expected_dimension: int | None = None) -> list[float]:
    """Validate that an embedding has finite values and matches expected dimension."""
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dimension}, got {len(vector)}"
        )

    clean_vector: list[float] = []
    for val in vector:
        if not math.isfinite(val):
            raise ValueError(f"Embedding contains non-finite value: {val}")
        clean_vector.append(float(val))

    return clean_vector


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Deterministic, credential-free embedding provider for tests."""

    def __init__(self, dimension: int = 384, provider_name: str = "mock", model_name: str = "mock-embed-v1"):
        self._dimension = dimension
        self.provider_name = provider_name
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            hasher = hashlib.sha256(text.encode("utf-8"))
            digest = hasher.digest()
            raw_floats = []
            for i in range(self._dimension):
                byte_val = digest[i % len(digest)]
                raw_floats.append((byte_val / 127.5) - 1.0)

            norm = math.sqrt(sum(x * x for x in raw_floats)) or 1.0
            unit_vector = [x / norm for x in raw_floats]
            results.append(validate_embedding(unit_vector, self._dimension))

        return results


class UnavailableEmbeddingProvider:
    """Provider simulating unavailable embedding service."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("Embedding service unavailable")
