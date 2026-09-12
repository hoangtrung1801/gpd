from datetime import datetime, timedelta, timezone
import json
from typing import Any
from sqlalchemy import select, update, text
from sqlalchemy.orm import Session

from gpd.jobs.models import Job, JobAttempt
from gpd.sources.models import utc_now_iso


class JobRepository:
    def __init__(self, session: Session, clock: Any = None):
        self.session = session
        self._clock = clock

    def _now(self) -> datetime:
        if self._clock is not None and hasattr(self._clock, "now"):
            now_val = self._clock.now()
            if isinstance(now_val, datetime):
                return now_val
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._now().isoformat()

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        project_id: str | None = None,
        max_attempts: int = 3,
    ) -> Job:
        if idempotency_key is not None:
            existing = self.session.execute(
                select(Job).where(Job.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing is not None:
                return existing

        now_iso = self._now_iso()
        job = Job(
            project_id=project_id,
            type=job_type,
            state="queued",
            idempotency_key=idempotency_key,
            payload_json=json.dumps(payload) if payload is not None else None,
            max_attempts=max_attempts,
            attempts=0,
            progress=0.0,
            created_at=now_iso,
            updated_at=now_iso,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_id(self, job_id: str) -> Job | None:
        return self.session.execute(
            select(Job).where(Job.id == job_id)
        ).scalar_one_or_none()

    def claim(self, worker_id: str, lease_seconds: int = 30) -> Job | None:
        now_dt = self._now()
        now_iso = now_dt.isoformat()
        lease_expires_dt = now_dt + timedelta(seconds=lease_seconds)
        lease_expires_iso = lease_expires_dt.isoformat()

        # Atomic claim statement via subquery with LIMIT 1
        claim_sql = text("""
            UPDATE jobs
            SET state = 'running',
                worker_id = :worker_id,
                lease_expires_at = :lease_expires_at,
                attempts = attempts + 1,
                updated_at = :now_iso
            WHERE id = (
                SELECT id FROM jobs
                WHERE state = 'queued'
                   OR (state = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < :now_iso)
                ORDER BY created_at ASC
                LIMIT 1
            )
            RETURNING id, project_id, type, state, idempotency_key, payload_json,
                      result_json, progress, attempts, max_attempts, worker_id,
                      lease_expires_at, error_category, error_message, created_at,
                      updated_at, completed_at
        """)

        result = self.session.execute(
            claim_sql,
            {
                "worker_id": worker_id,
                "lease_expires_at": lease_expires_iso,
                "now_iso": now_iso,
            },
        ).fetchone()

        if result is None:
            return None

        # Re-fetch as ORM object and refresh attributes from DB
        job_id = result.id
        job = self.session.get(Job, job_id)
        if job is None:
            return None
        self.session.refresh(job)

        # Record attempt
        attempt = JobAttempt(
            job_id=job.id,
            attempt_number=job.attempts,
            worker_id=worker_id,
            state="running",
            started_at=now_iso,
        )
        self.session.add(attempt)
        self.session.flush()

        return job

    def renew_lease(self, job_id: str, worker_id: str, lease_seconds: int = 30) -> bool:
        now_dt = self._now()
        lease_expires_iso = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        now_iso = now_dt.isoformat()

        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.worker_id == worker_id,
                Job.state == "running",
            )
            .values(
                lease_expires_at=lease_expires_iso,
                updated_at=now_iso,
            )
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount > 0

    def complete(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        now_iso = self._now_iso()
        job = self.get_by_id(job_id)
        if job is not None:
            job.state = "succeeded"
            job.result_json = json.dumps(result) if result is not None else None
            job.progress = 1.0
            job.completed_at = now_iso
            job.updated_at = now_iso

            # Update latest attempt
            latest_attempt = self.session.execute(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id)
                .order_by(JobAttempt.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_attempt is not None and latest_attempt.finished_at is None:
                latest_attempt.state = "succeeded"
                latest_attempt.finished_at = now_iso

            self.session.flush()

    def fail(
        self,
        job_id: str,
        error_message: str,
        error_category: str | None = None,
        retryable: bool = False,
        backoff_seconds: int = 0,
    ) -> None:
        now_dt = self._now()
        now_iso = now_dt.isoformat()
        job = self.get_by_id(job_id)
        if job is None:
            return

        if retryable and job.attempts < job.max_attempts:
            job.state = "queued"
            job.worker_id = None
            if backoff_seconds > 0:
                job.lease_expires_at = (now_dt + timedelta(seconds=backoff_seconds)).isoformat()
            else:
                job.lease_expires_at = None
            job.error_message = error_message
            job.error_category = error_category
            job.updated_at = now_iso
        else:
            job.state = "failed"
            job.error_message = error_message
            job.error_category = error_category
            job.completed_at = now_iso
            job.updated_at = now_iso

        latest_attempt = self.session.execute(
            select(JobAttempt)
            .where(JobAttempt.job_id == job_id)
            .order_by(JobAttempt.attempt_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_attempt is not None and latest_attempt.finished_at is None:
            latest_attempt.state = "failed"
            latest_attempt.error_message = error_message
            latest_attempt.finished_at = now_iso

        self.session.flush()

    def cancel(self, job_id: str) -> bool:
        now_iso = self._now_iso()
        job = self.get_by_id(job_id)
        if job is not None and job.state in ("queued", "running"):
            job.state = "cancelled"
            job.completed_at = now_iso
            job.updated_at = now_iso
            self.session.flush()
            return True
        return False

    def requeue_expired(self) -> int:
        now_iso = self._now_iso()
        stmt = (
            update(Job)
            .where(
                Job.state == "running",
                (Job.lease_expires_at.is_(None)) | (Job.lease_expires_at < now_iso),
            )
            .values(
                state="queued",
                worker_id=None,
                lease_expires_at=None,
                updated_at=now_iso,
            )
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount

    def record_progress(self, job_id: str, progress: float) -> None:
        now_iso = self._now_iso()
        stmt = (
            update(Job)
            .where(Job.id == job_id)
            .values(
                progress=min(1.0, max(0.0, progress)),
                updated_at=now_iso,
            )
        )
        self.session.execute(stmt)
        self.session.flush()

    def list_by_project(
        self, project_id: str | None = None, limit: int = 50, state: str | None = None
    ) -> list[Job]:
        stmt = select(Job)
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
        if state is not None:
            stmt = stmt.where(Job.state == state)
        stmt = stmt.order_by(Job.created_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
