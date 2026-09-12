import hashlib
import json
from typing import Any
from sqlalchemy import select

from gpd.api.errors import ApiException
from gpd.db.engine import Database
from gpd.db.models import IdempotencyKey
from gpd.jobs.models import Job
from gpd.jobs.repository import JobRepository
from gpd.sources.models import Source
from gpd.sources.parsers import (
    SourceValidationError,
    compute_content_hash,
    validate_and_normalize_content,
)
from gpd.sources.repository import SourceRepository
from gpd.sources.schemas import (
    SourceChunkResponse,
    SourceCreate,
    SourceDetailResponse,
    SourceIngestResult,
    SourceResponse,
    SourceSpanResponse,
)


def _to_source_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        project_id=source.project_id,
        type=source.type,
        title=source.title,
        canonical_ref=source.canonical_ref,
        author=source.author,
        captured_at=source.captured_at,
        content_hash=source.content_hash,
        state=source.state,
        error_message=source.error_message,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _to_source_detail_response(source: Source) -> SourceDetailResponse:
    spans = [
        SourceSpanResponse(
            id=span.id,
            locator=span.locator,
            content=span.content,
            checksum=span.checksum,
            created_at=span.created_at,
        )
        for span in source.spans
    ]
    chunks = [
        SourceChunkResponse(
            id=chunk.id,
            locator=chunk.locator,
            chunk_text=chunk.chunk_text,
            token_estimate=chunk.token_estimate,
            created_at=chunk.created_at,
        )
        for chunk in source.chunks
    ]
    return SourceDetailResponse(
        id=source.id,
        project_id=source.project_id,
        type=source.type,
        title=source.title,
        canonical_ref=source.canonical_ref,
        author=source.author,
        captured_at=source.captured_at,
        content_hash=source.content_hash,
        state=source.state,
        error_message=source.error_message,
        created_at=source.created_at,
        updated_at=source.updated_at,
        content=source.raw_content,
        spans=spans,
        chunks=chunks,
    )


class SourceService:
    def __init__(self, database: Database):
        self.database = database

    async def ingest(
        self,
        project_id: str,
        data: SourceCreate,
        idempotency_key: str | None = None,
    ) -> SourceIngestResult:
        """Ingest an immutable source with content-hash dedup and idempotency checking."""
        try:
            normalized_content = validate_and_normalize_content(data.content)
        except SourceValidationError as e:
            status_code = 413 if e.code == "content_too_large" else 422
            raise ApiException(status_code=status_code, code=e.code, message=e.message)

        content_hash = compute_content_hash(normalized_content)
        endpoint = f"/api/v1/projects/{project_id}/sources"
        request_dict = {
            "type": data.type,
            "title": data.title,
            "canonical_ref": data.canonical_ref,
            "author": data.author,
            "content_hash": content_hash,
        }
        request_hash = hashlib.sha256(
            json.dumps(request_dict, sort_keys=True).encode("utf-8")
        ).hexdigest()

        def _transaction() -> SourceIngestResult:
            with self.database.session() as session:
                source_repo = SourceRepository(session)
                job_repo = JobRepository(session)

                # 1. Idempotency Key check
                if idempotency_key is not None:
                    stmt = select(IdempotencyKey).where(
                        IdempotencyKey.endpoint == endpoint,
                        IdempotencyKey.key == idempotency_key,
                    )
                    existing_idemp = session.execute(stmt).scalar_one_or_none()
                    if existing_idemp is not None:
                        if existing_idemp.request_hash != request_hash:
                            raise ApiException(
                                status_code=409,
                                code="idempotency_conflict",
                                message="Idempotency key already used with different payload",
                            )
                        cached_body = json.loads(existing_idemp.response_body)
                        data_dict = cached_body.get("data", {})
                        return SourceIngestResult(
                            source_id=data_dict.get("source_id"),
                            job_id=data_dict.get("job_id"),
                            state=data_dict.get("state", "queued"),
                            reused=True,
                            content_hash=data_dict.get("content_hash", content_hash),
                        )

                # 2. Content-hash deduplication: (project_id, content_hash, type)
                existing_source = source_repo.find_by_content_hash(
                    project_id=project_id,
                    content_hash=content_hash,
                    source_type=data.type,
                )
                if existing_source is not None:
                    res = SourceIngestResult(
                        source_id=existing_source.id,
                        job_id=None,
                        state=existing_source.state,
                        reused=True,
                        content_hash=existing_source.content_hash,
                    )
                    if idempotency_key is not None:
                        idemp_record = IdempotencyKey(
                            endpoint=endpoint,
                            key=idempotency_key,
                            request_hash=request_hash,
                            response_status=202,
                            response_body=json.dumps(
                                {
                                    "ok": True,
                                    "data": res.model_dump(mode="json"),
                                    "warnings": [],
                                    "error": None,
                                }
                            ),
                        )
                        session.merge(idemp_record)
                        session.commit()
                    return res

                # 3. New source creation
                source = source_repo.create(
                    project_id=project_id,
                    source_type=data.type,
                    title=data.title,
                    raw_content=normalized_content,
                    content_hash=content_hash,
                    canonical_ref=data.canonical_ref,
                    author=data.author,
                )

                # 4. Enqueue background ingestion job
                job = job_repo.enqueue(
                    job_type="ingest_source",
                    payload={"source_id": source.id, "project_id": project_id},
                    idempotency_key=f"ingest_source:{source.id}",
                    project_id=project_id,
                )

                res = SourceIngestResult(
                    source_id=source.id,
                    job_id=job.id,
                    state=source.state,
                    reused=False,
                    content_hash=source.content_hash,
                )

                # 5. Store Idempotency key if given
                if idempotency_key is not None:
                    idemp_record = IdempotencyKey(
                        endpoint=endpoint,
                        key=idempotency_key,
                        request_hash=request_hash,
                        response_status=202,
                        response_body=json.dumps(
                            {
                                "ok": True,
                                "data": res.model_dump(mode="json"),
                                "warnings": [],
                                "error": None,
                            }
                        ),
                    )
                    session.merge(idemp_record)

                session.commit()
                return res

        return await self.database.write(_transaction)

    async def get_by_id(self, source_id: str, with_details: bool = True) -> SourceDetailResponse | None:
        def _get():
            with self.database.session() as session:
                repo = SourceRepository(session)
                source = repo.get_by_id(source_id, with_details=with_details)
                if source is None:
                    return None
                return _to_source_detail_response(source) if with_details else _to_source_response(source)

        return await self.database.write(_get)

    async def list_by_project(
        self, project_id: str, limit: int = 50, cursor: str | None = None
    ) -> list[SourceResponse]:
        def _list():
            with self.database.session() as session:
                repo = SourceRepository(session)
                sources = repo.list_by_project(project_id, limit=limit, cursor=cursor)
                return [_to_source_response(s) for s in sources]

        return await self.database.write(_list)
