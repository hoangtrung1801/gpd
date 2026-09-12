import re
from gpd.knowledge.workflows.contradiction import Claim, ContradictionResult


class ContradictionDetector:
    VERSION = "1.0"

    OPPOSING_TERMS = [
        (r"\b(three|3)\s*(times|retries)?\b", r"\b(one|1|single)\s*(time|retry)?\b"),
        (r"\benable(d)?\b", r"\bdisable(d)?\b"),
        (r"\ballow(ed)?\b", r"\b(disallow(ed)?|forbid(den)?|block(ed)?)\b"),
        (r"\breduced\b", r"\bincreased\b"),
        (r"\bsynchronous\b", r"\basynchronous\b"),
        (r"\btrue\b", r"\bfalse\b"),
    ]

    def detect(self, claim_a: Claim, claim_b: Claim) -> ContradictionResult:
        ev_ids = list(dict.fromkeys(claim_a.evidence_ids + claim_b.evidence_ids))
        if len(ev_ids) < 2:
            ev_ids = [claim_a.id, claim_b.id]

        text_a = f"{claim_a.title} {claim_a.content}".lower()
        text_b = f"{claim_b.title} {claim_b.content}".lower()

        # Check for direct opposing patterns on same topic
        is_opposing = False
        reason = ""

        # Topic overlap
        words_a = set(re.findall(r"\w{4,}", text_a))
        words_b = set(re.findall(r"\w{4,}", text_b))
        overlap = words_a.intersection(words_b)

        if overlap:
            for pat1, pat2 in self.OPPOSING_TERMS:
                match1_a = re.search(pat1, text_a)
                match2_b = re.search(pat2, text_b)
                match2_a = re.search(pat2, text_a)
                match1_b = re.search(pat1, text_b)

                if (match1_a and match2_b) or (match2_a and match1_b):
                    is_opposing = True
                    reason = f"Opposing directives detected regarding {', '.join(sorted(overlap)[:3])}."
                    break

        if is_opposing:
            return ContradictionResult(
                classification="contradictory",
                confidence=0.88,
                explanation=f"Contradiction detected: '{claim_a.title}' asserts '{claim_a.content}' while '{claim_b.title}' asserts '{claim_b.content}'. {reason}",
                evidence_ids=ev_ids,
            )

        # Check if one updates/supersedes the other on same subject
        if "update" in text_b or "reduced" in text_b or "new" in text_b:
            if overlap:
                return ContradictionResult(
                    classification="ambiguous",
                    confidence=0.72,
                    explanation=f"Potential version conflict between '{claim_a.title}' and '{claim_b.title}'.",
                    evidence_ids=ev_ids,
                )

        return ContradictionResult(
            classification="compatible",
            confidence=0.25,
            explanation=f"Claims '{claim_a.title}' and '{claim_b.title}' appear compatible.",
            evidence_ids=ev_ids,
        )
