from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gpd.db.models import IdempotencyKey, Project, Repository, new_uuid, utc_now_iso


class ProjectRepository:
    def get_by_id(self, session: Session, project_id: str) -> Project | None:
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.repositories))
        )
        return session.scalar(stmt)

    def get_by_name(self, session: Session, name: str) -> Project | None:
        stmt = (
            select(Project)
            .where(Project.name == name)
            .options(selectinload(Project.repositories))
        )
        return session.scalar(stmt)

    def list_all(self, session: Session) -> list[Project]:
        stmt = select(Project).options(selectinload(Project.repositories)).order_by(Project.name)
        return list(session.scalars(stmt).all())

    def create(
        self,
        session: Session,
        name: str,
        team_identifier: str | None,
        repository_root: str,
        remote_url: str | None,
        default_branch: str,
    ) -> Project:
        project_id = new_uuid()
        repo_id = new_uuid()
        now = utc_now_iso()

        project = Project(
            id=project_id,
            name=name,
            team_identifier=team_identifier,
            created_at=now,
        )
        repo = Repository(
            id=repo_id,
            project_id=project_id,
            root_path=repository_root,
            remote_url=remote_url,
            default_branch=default_branch,
            created_at=now,
        )
        project.repositories.append(repo)
        session.add(project)
        session.flush()
        return project

    def get_idempotency_key(
        self, session: Session, endpoint: str, key: str
    ) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.key == key,
        )
        return session.scalar(stmt)

    def save_idempotency_key(
        self,
        session: Session,
        endpoint: str,
        key: str,
        request_hash: str,
        status_code: int,
        response_body: str,
    ) -> IdempotencyKey:
        entry = IdempotencyKey(
            endpoint=endpoint,
            key=key,
            request_hash=request_hash,
            response_status=status_code,
            response_body=response_body,
            created_at=utc_now_iso(),
        )
        session.add(entry)
        session.flush()
        return entry
