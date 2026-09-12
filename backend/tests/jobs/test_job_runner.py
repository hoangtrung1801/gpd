import asyncio
from typing import Any
import pytest
from fastapi.testclient import TestClient

from gpd.db.engine import Database
from gpd.jobs.repository import JobRepository
from gpd.jobs.runner import JobRunner


def test_expired_job_lease_can_be_reclaimed(job_repository: JobRepository, clock: Any):
    """Test that an expired job lease can be reclaimed by another worker."""
    job = job_repository.enqueue("ingest_source", {"source_id": "source-1"}, "source-1:v1")
    claimed = job_repository.claim("worker-a", lease_seconds=30)
    assert claimed is not None
    assert claimed.worker_id == "worker-a"

    # Advance clock past lease expiry
    clock.advance(seconds=31)

    reclaimed = job_repository.claim("worker-b", lease_seconds=30)
    assert reclaimed is not None
    assert reclaimed.id == job.id
    assert reclaimed.worker_id == "worker-b"


@pytest.mark.asyncio
async def test_job_runner_executes_registered_handler(runner: JobRunner, database: Database):
    """Test that JobRunner executes registered handler and marks job as succeeded."""
    handled_payloads = []

    async def sample_handler(payload: dict[str, Any]) -> dict[str, Any]:
        handled_payloads.append(payload)
        return {"status": "processed"}

    runner.register("sample_task", sample_handler)

    def _enqueue():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.enqueue("sample_task", {"foo": "bar"}, idempotency_key="sample-1")
            session.commit()
            return job.id

    job_id = await database.write(_enqueue)

    worked = await runner.run_once("worker-test-1")
    assert worked is True
    assert len(handled_payloads) == 1
    assert handled_payloads[0]["foo"] == "bar"

    def _check():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.get_by_id(job_id)
            assert job is not None
            assert job.state == "succeeded"
            assert job.progress == 1.0

    await database.write(_check)


@pytest.mark.asyncio
async def test_job_runner_retry_with_backoff_on_failure(runner: JobRunner, database: Database):
    """Test that failing jobs are retried with backoff until max_attempts."""
    async def failing_handler(_payload: dict[str, Any]):
        raise RuntimeError("Transient worker error")

    runner.register("failing_task", failing_handler)

    def _enqueue():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.enqueue("failing_task", {"attempt": 1}, max_attempts=3)
            session.commit()
            return job.id

    job_id = await database.write(_enqueue)

    # First run fails -> backoff and queued
    worked = await runner.run_once("worker-failing")
    assert worked is True

    def _check():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.get_by_id(job_id)
            assert job is not None
            assert job.state == "queued"
            assert job.attempts == 1
            assert job.worker_id is None
            assert job.lease_expires_at is not None  # backoff set

    await database.write(_check)


@pytest.mark.asyncio
async def test_requeue_expired_jobs_on_startup(runner: JobRunner, database: Database):
    """Test that expired leased jobs are returned to queued on runner startup."""
    def _create_stale_job():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.enqueue("stale_task", {"val": 42})
            # Force into running with expired lease
            job.state = "running"
            job.worker_id = "dead-worker"
            job.lease_expires_at = "2020-01-01T00:00:00Z"
            session.commit()
            return job.id

    job_id = await database.write(_create_stale_job)

    requeued_count = await runner.requeue_expired_leases()
    assert requeued_count >= 1

    def _check():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.get_by_id(job_id)
            assert job is not None
            assert job.state == "queued"
            assert job.worker_id is None

    await database.write(_check)


def test_job_cancellation(job_repository: JobRepository):
    """Test cancelling a queued job."""
    job = job_repository.enqueue("to_cancel", {"key": "value"})
    assert job.state == "queued"

    cancelled = job_repository.cancel(job.id)
    assert cancelled is True

    updated_job = job_repository.get_by_id(job.id)
    assert updated_job is not None
    assert updated_job.state == "cancelled"


def test_get_job_api(client: TestClient, database: Database):
    """Test fetching job details via GET /api/v1/jobs/{job_id}."""
    def _create():
        with database.session() as session:
            repo = JobRepository(session)
            job = repo.enqueue("api_task", {"num": 100})
            session.commit()
            return job.id

    import asyncio
    job_id = asyncio.run(database.write(_create))

    res = client.get(f"/api/v1/jobs/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == job_id
    assert body["data"]["type"] == "api_task"
    assert body["data"]["state"] == "queued"
    assert body["data"]["payload"]["num"] == 100
