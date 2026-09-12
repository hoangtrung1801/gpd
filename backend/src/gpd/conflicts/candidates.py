import re
from typing import Sequence
from gpd.knowledge.workflows.contradiction import Claim


class CandidateGenerator:
    def generate_pairs(
        self,
        claims: Sequence[Claim],
        excluded_pairs: set[tuple[str, str]] | None = None,
    ) -> list[tuple[Claim, Claim]]:
        excluded = excluded_pairs or set()
        pairs: list[tuple[Claim, Claim]] = []

        # Compare pairs within the same project
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                c1 = claims[i]
                c2 = claims[j]
                if c1.project_id != c2.project_id:
                    continue
                if (c1.id, c2.id) in excluded or (c2.id, c1.id) in excluded:
                    continue
                if c1.content.strip() == c2.content.strip():
                    continue

                # Check topic overlap
                words1 = set(re.findall(r"\w{4,}", f"{c1.title} {c1.content}".lower()))
                words2 = set(re.findall(r"\w{4,}", f"{c2.title} {c2.content}".lower()))
                if words1.intersection(words2):
                    pairs.append((c1, c2))

        return pairs
