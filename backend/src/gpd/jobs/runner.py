import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any, Protocol

from gpd.db.engine import Database
from gpd.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class JobHandler(Protocol):
    async def __call__(self, payload: dict[str, Any]) -> Any: ...


class JobRunner:
    def __init__(
        self,
        database: Database,
        lease_seconds: int = 30,
        poll_interval: float = 1.0,
    ):
        self.database = database
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def has_handler(self, job_type: str) -> bool:
        return job_type in self._handlers

    async def requeue_expired_leases(self) -> int:
        def _requeue() -> int:
            with self.database.session() as session:
                repo = JobRepository(session)
                count = repo.requeue_expired()
                session.commit()
                return count

        return await self.database.write(_requeue)

    async def run_once(self, worker_id: str) -> bool:
        if not self._handlers:
            return False
        # 1. Claim a job atomically
        def _claim():
            with self.database.session() as session:
                repo = JobRepository(session)
                job = repo.claim(worker_id, lease_seconds=self.lease_seconds)
                if job is None:
                    return None
                payload = json.loads(job.payload_json) if job.payload_json else {}
                job_data = {
                    "id": job.id,
                    "type": job.type,
                    "payload": payload,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                }
                session.commit()
                return job_data

        job_info = await self.database.write(_claim)
        if job_info is None:
            return False

        job_id = job_info["id"]
        job_type = job_info["type"]
        payload = job_info["payload"]
        attempts = job_info["attempts"]

        handler = self._handlers.get(job_type)
        if handler is None:
            def _fail_unknown():
                with self.database.session() as session:
                    repo = JobRepository(session)
                    repo.fail(
                        job_id,
                        f"No handler registered for job type: {job_type}",
                        error_category="unhandled_type",
                        retryable=False,
                    )
                    session.commit()

            await self.database.write(_fail_unknown)
            return True

        # 2. Setup background lease renewer
        stop_renew = asyncio.Event()

        async def _lease_renewer():
            renew_interval = max(5.0, self.lease_seconds / 2.0)
            while not stop_renew.is_set():
                try:
                    await asyncio.wait_for(stop_renew.wait(), timeout=renew_interval)
                except asyncio.TimeoutError:
                    def _renew():
                        with self.database.session() as session:
                            repo = JobRepository(session)
                            ok = repo.renew_lease(job_id, worker_id, lease_seconds=self.lease_seconds)
                            session.commit()
                            return ok

                    try:
                        await self.database.write(_renew)
                    except Exception as e:
                        logger.warning(f"Failed to renew lease for job {job_id}: {e}")

        renewer_task = asyncio.create_task(_lease_renewer())

        # 3. Execute handler outside of DB write lock
        try:
            result = await handler(payload)
            stop_renew.set()
            renewer_task.cancel()
            try:
                await renewer_task
            except asyncio.CancelledError:
                pass

            # 4. Mark succeeded
            def _complete():
                with self.database.session() as session:
                    repo = JobRepository(session)
                    res_dict = result if isinstance(result, dict) else {"output": result}
                    repo.complete(job_id, result=res_dict)
                    session.commit()

            await self.database.write(_complete)
            return True

        except Exception as exc:
            stop_renew.set()
            renewer_task.cancel()
            try:
                await renewer_task
            except asyncio.CancelledError:
                pass

            # Bounded exponential backoff: min(300, 2 ** attempts)
            backoff_seconds = min(300, 2 ** attempts)
            error_message = str(exc)

            def _fail():
                with self.database.session() as session:
                    repo = JobRepository(session)
                    repo.fail(
                        job_id,
                        error_message=error_message,
                        error_category="execution_error",
                        retryable=True,
                        backoff_seconds=backoff_seconds,
                    )
                    session.commit()

            await self.database.write(_fail)
            return True

    async def run_forever(self, worker_id: str, stop: asyncio.Event) -> None:
        try:
            requeued = await self.requeue_expired_leases()
            if requeued > 0:
                logger.info(f"Requeued {requeued} expired jobs on startup")
        except Exception as e:
            logger.warning(f"Failed to requeue expired jobs at startup: {e}")

        while not stop.is_set():
            try:
                worked = await self.run_once(worker_id)
                if not worked:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=self.poll_interval)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in job worker loop: {exc}")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass
