from collections.abc import Sequence
from typing import Any

BOOSTS: dict[str, float] = {
    "direct_task_link": 0.40,
    "exact_file_link": 0.30,
    "same_component": 0.20,
    "confirmed_knowledge": 0.15,
    "source_conversation": 0.10,
}

PENALTIES: dict[str, float] = {
    "unconfirmed_knowledge": -0.10,
    "superseded_knowledge": -1.00,
    "stale_source": -0.05,
}


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> dict[str, float]:
    """Calculate reciprocal rank fusion scores across multiple ordered lists of chunk IDs."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


def apply_boosts_and_penalties(
    base_score: float,
    metadata: dict[str, Any],
    query_task_id: str | None = None,
    query_files: Sequence[str] | None = None,
    query_component: str | None = None,
) -> tuple[float, list[str]]:
    """Apply domain boosts and penalties based on relationship metadata and query parameters."""
    score = base_score
    reasons: list[str] = []

    # 1. Direct task link
    chunk_task_ids = metadata.get("linked_task_ids", [])
    if isinstance(chunk_task_ids, str):
        chunk_task_ids = [chunk_task_ids]
    if query_task_id and query_task_id in chunk_task_ids:
        score += BOOSTS["direct_task_link"]
        reasons.append("direct_task_link")
    elif metadata.get("direct_task_link"):
        score += BOOSTS["direct_task_link"]
        reasons.append("direct_task_link")

    # 2. Exact file link
    chunk_files = metadata.get("related_files", [])
    if isinstance(chunk_files, str):
        chunk_files = [chunk_files]
    if query_files:
        normalized_q_files = set(f.strip().lower() for f in query_files)
        if any(f.strip().lower() in normalized_q_files for f in chunk_files):
            score += BOOSTS["exact_file_link"]
            reasons.append("exact_file_link")
    elif metadata.get("exact_file_link"):
        score += BOOSTS["exact_file_link"]
        reasons.append("exact_file_link")

    # 3. Same component
    chunk_component = metadata.get("component")
    if query_component and chunk_component and query_component.lower() == chunk_component.lower():
        score += BOOSTS["same_component"]
        reasons.append("same_component")
    elif metadata.get("same_component"):
        score += BOOSTS["same_component"]
        reasons.append("same_component")

    # 4. Confirmed / Unconfirmed / Superseded knowledge status
    status = metadata.get("status")
    if status == "confirmed" or metadata.get("confirmed_knowledge"):
        score += BOOSTS["confirmed_knowledge"]
        reasons.append("confirmed_knowledge")
    elif status == "unconfirmed" or metadata.get("unconfirmed_knowledge"):
        score += PENALTIES["unconfirmed_knowledge"]
        reasons.append("unconfirmed_knowledge")
    elif status == "superseded" or metadata.get("superseded_knowledge"):
        score += PENALTIES["superseded_knowledge"]
        reasons.append("superseded_knowledge")

    # 5. Source conversation
    source_type = metadata.get("source_type")
    if source_type in ("slack_thread", "conversation") or metadata.get("source_conversation"):
        score += BOOSTS["source_conversation"]
        reasons.append("source_conversation")

    # 6. Stale source
    if metadata.get("is_stale") or metadata.get("stale_source"):
        score += PENALTIES["stale_source"]
        reasons.append("stale_source")

    return score, reasons
