import hashlib
import json
from uuid import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gpd.api.errors import ApiException
from gpd.audit.service import append as append_audit
from gpd.db.engine import Database
from gpd.projects.repository import ProjectRepository
from gpd.projects.schemas import Project, ProjectCreate, Repository


class ProjectService:
    def __init__(self, database: Database, repository: ProjectRepository | None = None):
        self.database = database
        self.repository = repository or ProjectRepository()

    def _compute_request_hash(self, data: ProjectCreate) -> str:
        dump = data.model_dump(mode="json")
        canonical = json.dumps(dump, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def register(
        self, data: ProjectCreate, idempotency_key: str | None = None
    ) -> Project:
        endpoint = "POST /api/v1/projects"
        request_hash = self._compute_request_hash(data)

        def _txn() -> Project:
            with self.database.session() as session:
                with session.begin():
                    if idempotency_key:
                        existing_key = self.repository.get_idempotency_key(
                            session, endpoint, idempotency_key
                        )
                        if existing_key is not None:
                            if existing_key.request_hash == request_hash:
                                payload = json.loads(existing_key.response_body)
                                project = Project.model_validate(payload)
                                project.is_replay = True
                                return project
                            else:
                                raise ApiException(
                                    status_code=409,
                                    code="idempotency_conflict",
                                    message="Idempotency key mismatch with different payload",
                                )

                    # Check uniqueness before insert
                    if self.repository.get_by_name(session, data.name) is not None:
                        raise ApiException(
                            status_code=409,
                            code="project_already_exists",
                            message=f"Project with name '{data.name}' already exists",
                        )

                    try:
                        proj_model = self.repository.create(
                            session=session,
                            name=data.name,
                            team_identifier=data.team_identifier,
                            repository_root=data.repository_root,
                            remote_url=data.remote_url,
                            default_branch=data.default_branch,
                        )

                        append_audit(
                            session,
                            actor="system",
                            action="project.create",
                            target=f"project:{proj_model.id}",
                            metadata={
                                "name": proj_model.name,
                                "repository_root": data.repository_root,
                            },
                        )

                        # Build project schema
                        proj_schema = Project(
                            id=UUID(proj_model.id),
                            name=proj_model.name,
                            team_identifier=proj_model.team_identifier,
                            created_at=proj_model.created_at,
                            repositories=[
                                Repository(
                                    id=UUID(r.id),
                                    project_id=UUID(r.project_id),
                                    root_path=r.root_path,
                                    remote_url=r.remote_url,
                                    default_branch=r.default_branch,
                                )
                                for r in proj_model.repositories
                            ],
                        )

                        if idempotency_key:
                            response_body = json.dumps(proj_schema.model_dump(mode="json"))
                            self.repository.save_idempotency_key(
                                session=session,
                                endpoint=endpoint,
                                key=idempotency_key,
                                request_hash=request_hash,
                                status_code=200,
                                response_body=response_body,
                            )

                        proj_schema.is_replay = False
                        return proj_schema
                    except IntegrityError as e:
                        raise ApiException(
                            status_code=409,
                            code="conflict",
                            message="Database constraint violation on project registration",
                        ) from e

        return await self.database.write(_txn)

    async def get_by_id(self, project_id: UUID | str) -> Project | None:
        def _query() -> Project | None:
            with self.database.session() as session:
                proj = self.repository.get_by_id(session, str(project_id))
                if proj is None:
                    return None
                return Project(
                    id=UUID(proj.id),
                    name=proj.name,
                    team_identifier=proj.team_identifier,
                    created_at=proj.created_at,
                    repositories=[
                        Repository(
                            id=UUID(r.id),
                            project_id=UUID(r.project_id),
                            root_path=r.root_path,
                            remote_url=r.remote_url,
                            default_branch=r.default_branch,
                        )
                        for r in proj.repositories
                    ],
                )

        return await self.database.write(_query)

    async def list_all(self) -> list[Project]:
        def _query() -> list[Project]:
            with self.database.session() as session:
                projs = self.repository.list_all(session)
                return [
                    Project(
                        id=UUID(p.id),
                        name=p.name,
                        team_identifier=p.team_identifier,
                        created_at=p.created_at,
                        repositories=[
                            Repository(
                                id=UUID(r.id),
                                project_id=UUID(r.project_id),
                                root_path=r.root_path,
                                remote_url=r.remote_url,
                                default_branch=r.default_branch,
                            )
                            for r in p.repositories
                        ],
                    )
                    for p in projs
                ]

        return await self.database.write(_query)
