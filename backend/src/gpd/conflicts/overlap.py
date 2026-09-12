from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Sequence
from pydantic import BaseModel, Field

from gpd.sessions.schemas import ConflictEvidenceSchema, OverlapWarning


class OverlapSessionInput(BaseModel):
    session_id: str
    task_id: str | None = None
    files: list[str] = Field(default_factory=list)
    component: str | None = None
    last_seen_at: str
    status: str = "active"


class OverlapDetector:
    EXACT_FILE_WEIGHT = 1.0
    SAME_MODULE_WEIGHT = 0.6
    SAME_COMPONENT_WEIGHT = 0.5
    SAME_TASK_WEIGHT = 0.4
    SHARED_KNOWLEDGE_WEIGHT = 0.2

    HIGH_THRESHOLD = 1.0
    MEDIUM_THRESHOLD = 0.6
    LOW_THRESHOLD = 0.4

    def compare(
        self,
        current: OverlapSessionInput,
        other: OverlapSessionInput,
    ) -> OverlapWarning | None:
        evidence: list[ConflictEvidenceSchema] = []
        weights_sum = 0.0

        current_files = set(current.files)
        other_files = set(other.files)

        # 1. Exact file matches
        exact_matches = current_files.intersection(other_files)
        for f in sorted(exact_matches):
            weights_sum += self.EXACT_FILE_WEIGHT
            evidence.append(
                ConflictEvidenceSchema(
                    kind="exact_file",
                    target_type="file",
                    target_id=f,
                    score_component=self.EXACT_FILE_WEIGHT,
                    detail=f"Both sessions are modifying file '{f}'",
                )
            )

        # 2. Same module / directory prefix (if not already exact match)
        current_modules = {str(Path(f).parent) for f in current_files if str(Path(f).parent) not in (".", "")}
        other_modules = {str(Path(f).parent) for f in other_files if str(Path(f).parent) not in (".", "")}
        shared_modules = current_modules.intersection(other_modules)
        for m in sorted(shared_modules):
            # Only add if exact match wasn't already triggered on all files in this module
            weights_sum += self.SAME_MODULE_WEIGHT
            evidence.append(
                ConflictEvidenceSchema(
                    kind="same_module",
                    target_type="file",
                    target_id=m,
                    score_component=self.SAME_MODULE_WEIGHT,
                    detail=f"Both sessions touch files in module '{m}'",
                )
            )

        # 3. Same component
        if current.component and other.component and current.component == other.component:
            weights_sum += self.SAME_COMPONENT_WEIGHT
            evidence.append(
                ConflictEvidenceSchema(
                    kind="same_component",
                    target_type="task",
                    target_id=current.component,
                    score_component=self.SAME_COMPONENT_WEIGHT,
                    detail=f"Both sessions share component '{current.component}'",
                )
            )

        # 4. Same or related task
        if current.task_id and other.task_id and current.task_id == other.task_id:
            weights_sum += self.SAME_TASK_WEIGHT
            evidence.append(
                ConflictEvidenceSchema(
                    kind="same_task",
                    target_type="task",
                    target_id=current.task_id,
                    score_component=self.SAME_TASK_WEIGHT,
                    detail=f"Both sessions are assigned to the same task '{current.task_id}'",
                )
            )

        if not evidence:
            return None

        score = min(1.0, weights_sum)
        if score < self.LOW_THRESHOLD:
            return None

        if score >= self.HIGH_THRESHOLD:
            severity = "high"
            suggested_action = (
                f"Avoid editing overlapping files until session {other.session_id} completes"
            )
        elif score >= self.MEDIUM_THRESHOLD:
            severity = "medium"
            suggested_action = (
                f"Coordinate with session {other.session_id} before editing shared module"
            )
        else:
            severity = "low"
            suggested_action = (
                f"Continue work (informational overlap detected with session {other.session_id})"
            )

        explanation = f"Work overlap detected with active session {other.session_id} (score: {score:.2f})."

        return OverlapWarning(
            severity=severity,
            score=score,
            explanation=explanation,
            suggested_action=suggested_action,
            evidence=evidence,
            conflicting_session_id=other.session_id,
        )


def is_active_session(session: OverlapSessionInput, expiry_seconds: int = 120) -> bool:
    if session.status != "active":
        return False
    try:
        last_seen = datetime.fromisoformat(session.last_seen_at)
        now = datetime.now(timezone.utc)
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        return (now - last_seen).total_seconds() <= expiry_seconds
    except Exception:
        return False


def detect_work_overlaps(
    current: OverlapSessionInput,
    other_sessions: Sequence[OverlapSessionInput],
    detector: OverlapDetector | None = None,
    expiry_seconds: int = 120,
) -> list[OverlapWarning]:
    resolved_detector = detector or OverlapDetector()
    warnings: list[OverlapWarning] = []
    for other in other_sessions:
        if other.session_id == current.session_id:
            continue
        if not is_active_session(other, expiry_seconds=expiry_seconds):
            continue
        warning = resolved_detector.compare(current, other)
        if warning:
            warnings.append(warning)
    return warnings
