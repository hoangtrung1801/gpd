import asyncio

from fastapi.testclient import TestClient

from gpd.db.engine import Database
from gpd.jobs.repository import JobRepository


def _enqueue(database: Database) -> str:
    def _create():
        with database.session() as session:
            job = JobRepository(session).enqueue("api_task", {"num": 1})
            session.commit()
            return job.id

    return asyncio.run(database.write(_create))


def test_cancel_queued_job(client: TestClient, database: Database):
    job_id = _enqueue(database)

    res = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert res.status_code == 200
    assert res.json()["data"]["state"] == "cancelled"


def test_retry_cancelled_job_requeues(client: TestClient, database: Database):
    job_id = _enqueue(database)
    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200

    res = client.post(f"/api/v1/jobs/{job_id}/retry")

    assert res.status_code == 200
    assert res.json()["data"]["state"] == "queued"


def test_retry_queued_job_is_409(client: TestClient, database: Database):
    job_id = _enqueue(database)

    res = client.post(f"/api/v1/jobs/{job_id}/retry")

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "job_not_retryable"


def test_cancel_finished_job_is_409(client: TestClient, database: Database):
    job_id = _enqueue(database)
    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200

    res = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "job_not_cancellable"


def test_retry_unknown_job_is_404(client: TestClient):
    res = client.post("/api/v1/jobs/does-not-exist/retry")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "job_not_found"
