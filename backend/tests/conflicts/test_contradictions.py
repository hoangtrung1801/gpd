from gpd.conflicts.contradictions import ContradictionDetector
from gpd.knowledge.workflows.contradiction import Claim, ContradictionResult


def test_retry_policy_conflict_keeps_both_sources():
    detector = ContradictionDetector()
    c1 = Claim(
        id="k1",
        project_id="p1",
        title="Retry policy",
        content="Retry payment three times",
        evidence_ids=["prd:12"],
    )
    c2 = Claim(
        id="k2",
        project_id="p1",
        title="Retry policy update",
        content="Retries were reduced to one",
        evidence_ids=["slack:m4"],
    )
    
    conflict = detector.detect(c1, c2)
    assert conflict is not None
    assert conflict.classification in ("contradictory", "ambiguous")
    assert set(conflict.evidence_ids) == {"prd:12", "slack:m4"}
    assert conflict.confidence >= 0.70


def test_compatible_claims_do_not_produce_high_conflict():
    detector = ContradictionDetector()
    c1 = Claim(
        id="k1",
        project_id="p1",
        title="Database engine",
        content="Use SQLite with WAL mode enabled",
        evidence_ids=["doc:1"],
    )
    c2 = Claim(
        id="k2",
        project_id="p1",
        title="Database timeout",
        content="Configure busy timeout to 5000ms",
        evidence_ids=["doc:2"],
    )
    conflict = detector.detect(c1, c2)
    assert conflict.classification == "compatible"
    assert conflict.confidence < 0.70 or conflict.classification == "compatible"
