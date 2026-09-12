from datetime import datetime, timezone, timedelta
from gpd.conflicts.overlap import OverlapDetector, OverlapSessionInput, detect_work_overlaps


def _session(
    session_id: str = "s1",
    task_id: str | None = "BUG-1",
    files: list[str] | None = None,
    component: str | None = None,
    last_seen_at: str | None = None,
    status: str = "active",
) -> OverlapSessionInput:
    now = datetime.now(timezone.utc).isoformat()
    return OverlapSessionInput(
        session_id=session_id,
        task_id=task_id,
        files=files or [],
        component=component,
        last_seen_at=last_seen_at or now,
        status=status,
    )


def test_same_file_in_active_sessions_is_high_overlap():
    detector = OverlapDetector()
    s1 = _session("s1", task_id="BUG-1", files=["src/payment/service.ts"])
    s2 = _session("s2", task_id="TASK-2", files=["src/payment/service.ts"])
    
    conflict = detector.compare(s1, s2)
    assert conflict is not None
    assert conflict.severity == "high"
    assert any(e.kind == "exact_file" for e in conflict.evidence)
    assert conflict.score >= 1.0
    assert "Avoid editing" in conflict.suggested_action


def test_same_module_overlap_is_medium_severity():
    detector = OverlapDetector()
    s1 = _session("s1", task_id="BUG-1", files=["src/payment/service.ts"])
    s2 = _session("s2", task_id="TASK-2", files=["src/payment/handler.ts"])
    
    conflict = detector.compare(s1, s2)
    assert conflict is not None
    assert conflict.severity == "medium"
    assert conflict.score >= 0.6
    assert any(e.kind == "same_module" for e in conflict.evidence)
    assert "Coordinate" in conflict.suggested_action


def test_no_false_warning_for_stale_session():
    detector = OverlapDetector()
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=130)).isoformat()
    s1 = _session("s1", task_id="BUG-1", files=["src/payment/service.ts"])
    s2 = _session("s2", task_id="TASK-2", files=["src/payment/service.ts"], last_seen_at=stale_time, status="stale")
    
    conflicts = detect_work_overlaps(s1, [s2])
    assert len(conflicts) == 0


def test_score_is_capped_at_one():
    detector = OverlapDetector()
    s1 = _session("s1", task_id="BUG-1", files=["src/payment/service.ts"])
    s2 = _session("s2", task_id="BUG-1", files=["src/payment/service.ts"])
    
    conflict = detector.compare(s1, s2)
    assert conflict is not None
    assert conflict.score == 1.0
