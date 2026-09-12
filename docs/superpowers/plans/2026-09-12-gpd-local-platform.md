# GPD Local Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build GPD from scratch as a local shared-memory platform with a FastAPI backend, SQLite hybrid search, Slack-to-bug workflow, React dashboard, developer CLI, agent-neutral MCP server, work coordination, conflict detection, and reviewed knowledge reuse.

**Architecture:** A Python FastAPI application owns all domain rules and the single SQLite database. A React browser app, TypeScript CLI, TypeScript stdio MCP server, and Slack adapter use versioned HTTP APIs; durable background jobs run LLM and indexing workflows without holding database transactions.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite WAL/FTS5, sqlite-vec, OpenAI-compatible LLM gateway, Node.js 24+, pnpm, TypeScript, React, Vite, TanStack Query, MCP TypeScript SDK, Pytest, Vitest, React Testing Library, Playwright, Docker Compose

**Spec:** docs/superpowers/specs/2026-09-12-gpd-architecture-design.md

## Global Constraints

- Python 3.12 or newer; Node.js 24 or newer.
- SQLite is the only database. Enable WAL, foreign keys, busy timeout, FTS5, and integrity checks.
- FastAPI is the sole SQLite owner; browser, CLI, MCP, and Slack clients never open gpd.db.
- Default database path is .gpd/gpd.db and repository configuration path is .gpd/config.json.
- Credentials stay in environment variables or the operating-system credential store, never SQLite or logs.
- Every generated fact retains source evidence and confidence; missing facts remain empty.
- Raw sources are immutable; derived records retain generator/schema versions.
- Durable knowledge changes require explicit human confirmation.
- Vector search degrades to FTS5 and direct relationships when sqlite-vec or embeddings are unavailable.
- All public HTTP APIs live below /api/v1 and mutations accept idempotency keys.
- CLI machine output uses the stable envelope {ok, data, warnings, error}.
- Normal CI is deterministic and credential-free; live Slack and LLM checks are opt-in.

---

## Planned Repository Structure

~~~text
.
├── .env.example
├── .gitignore
├── README.md
├── compose.yaml
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── pyproject.toml
├── uv.lock
├── tsconfig.base.json
├── backend/
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   ├── src/gpd/
│   │   ├── app.py
│   │   ├── settings.py
│   │   ├── api/
│   │   │   ├── errors.py
│   │   │   ├── dependencies.py
│   │   │   └── routers/
│   │   ├── db/
│   │   │   ├── engine.py
│   │   │   ├── models.py
│   │   │   └── migrations.py
│   │   ├── projects/
│   │   ├── sources/
│   │   ├── knowledge/
│   │   ├── tasks/
│   │   ├── conversations/
│   │   ├── context/
│   │   ├── sessions/
│   │   ├── conflicts/
│   │   ├── integrations/slack/
│   │   ├── llm/
│   │   ├── jobs/
│   │   ├── audit/
│   │   └── security/
│   └── tests/
├── apps/
│   ├── web/
│   ├── cli/
│   └── mcp/
├── packages/
│   ├── api-client/
│   ├── contracts/
│   └── config/
├── fixtures/
│   ├── demo-project/
│   ├── slack/
│   └── llm/
└── tests/e2e/
~~~

Each capability directory contains schemas.py, repository.py, service.py, and router.py only when that capability needs those responsibilities. Avoid generic utility modules; shared code belongs in the narrowest owning package.

---

### Task 1: Initialize the Monorepo and Health Boundary

**Files:**
- Create: .gitignore
- Create: .env.example
- Create: README.md
- Create: pyproject.toml
- Create: uv.lock
- Create: package.json
- Create: pnpm-workspace.yaml
- Create: tsconfig.base.json
- Create: backend/src/gpd/__init__.py
- Create: backend/src/gpd/settings.py
- Create: backend/src/gpd/app.py
- Create: backend/tests/conftest.py
- Create: backend/tests/test_health.py

**Interfaces:**
- Produces: create_app(settings: Settings | None = None) -> FastAPI
- Produces: GET /health -> {status: "ok", version: str, database: "pending"}
- Produces: root workspace commands lint, test, typecheck, dev

- [ ] **Step 1: Initialize Git and workspace metadata**

Run:

~~~bash
git init
git branch -M main
mkdir -p backend/src/gpd backend/tests apps packages fixtures tests/e2e
~~~

Write .gitignore with Python caches, virtual environments, node_modules, build output, .env, and .gpd/*.db plus SQLite WAL/SHM companions. Keep .gpd/config.json trackable because its schema contains only API URL and opaque project/repository/task identifiers.

- [ ] **Step 2: Write the failing health test**

~~~python
from fastapi.testclient import TestClient

from gpd.app import create_app
from gpd.settings import Settings


def test_health_reports_application_state(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "gpd.db"))
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "pending",
    }
~~~

- [ ] **Step 3: Run the test and verify the missing application fails**

Run: uv run pytest backend/tests/test_health.py -q

Expected: collection fails because gpd.app does not exist.

- [ ] **Step 4: Implement settings, application factory, and workspace commands**

~~~python
# backend/src/gpd/settings.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GPD_", env_file=".env")
    database_path: Path = Path(".gpd/gpd.db")
    api_host: str = "127.0.0.1"
    api_port: int = 7337
    app_version: str = "0.1.0"
~~~

~~~python
# backend/src/gpd/app.py
from fastapi import FastAPI
from gpd.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="GPD API", version=resolved.app_version)
    app.state.settings = resolved

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": resolved.app_version,
            "database": "pending",
        }

    return app


app = create_app()
~~~

Configure pyproject.toml with hatchling, the backend/src package path, Ruff, mypy, and Pytest. Configure the root package.json as a private pnpm workspace with lint, typecheck, test, and build scripts that fan out to apps and packages.

- [ ] **Step 5: Verify the foundation**

Run:

~~~bash
uv sync
uv run pytest backend/tests/test_health.py -q
uv run ruff check backend
uv run mypy backend/src
pnpm install
pnpm -r test --if-present
~~~

Expected: the health test passes and every configured check exits 0.

- [ ] **Step 6: Commit the foundation**

~~~bash
git add .
git commit -m "chore: initialize GPD monorepo"
~~~

---

### Task 2: Add SQLite Ownership, Project Registration, and Migrations

**Files:**
- Create: backend/alembic.ini
- Create: backend/migrations/env.py
- Create: backend/migrations/versions/0001_projects.py
- Create: backend/src/gpd/db/engine.py
- Create: backend/src/gpd/db/models.py
- Create: backend/src/gpd/db/migrations.py
- Create: backend/src/gpd/projects/schemas.py
- Create: backend/src/gpd/projects/repository.py
- Create: backend/src/gpd/projects/service.py
- Create: backend/src/gpd/projects/router.py
- Create: backend/src/gpd/api/errors.py
- Create: backend/src/gpd/api/dependencies.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/db/test_engine.py
- Test: backend/tests/projects/test_projects_api.py

**Interfaces:**
- Produces: Database.open(path: Path) -> Database
- Produces: ProjectService.register(ProjectCreate, idempotency_key: str) -> Project
- Produces: POST /api/v1/projects and GET /api/v1/projects/{project_id}
- Produces: Project {id: UUID, name: str, team_identifier: str | None, created_at: datetime}
- Produces: Repository {id: UUID, project_id: UUID, root_path: str, remote_url: str | None, default_branch: str}

- [ ] **Step 1: Write failing SQLite configuration and registration tests**

~~~python
def test_database_enables_required_pragmas(database):
    with database.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_register_project_is_idempotent(client, project_payload):
    headers = {"Idempotency-Key": "init-checkout"}
    first = client.post("/api/v1/projects", json=project_payload, headers=headers)
    second = client.post("/api/v1/projects", json=project_payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
~~~

- [ ] **Step 2: Run the focused tests**

Run: uv run pytest backend/tests/db/test_engine.py backend/tests/projects/test_projects_api.py -q

Expected: failures show missing Database and /api/v1/projects.

- [ ] **Step 3: Create the first migration and database owner**

The migration creates projects, repositories, idempotency_keys, and audit_events with UUID text primary keys, UTC timestamp text columns, foreign keys, unique project names, and unique repository roots.

~~~python
# backend/src/gpd/db/engine.py
class Database:
    def __init__(self, engine: Engine):
        self.engine = engine

    @classmethod
    def open(cls, path: Path) -> "Database":
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            "sqlite+pysqlite:///" + str(path),
            connect_args={"check_same_thread": False, "timeout": 5},
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return cls(engine)

    def connect(self):
        return self.engine.connect()
~~~

Run Alembic upgrades from an explicit management function before accepting requests. Do not auto-create tables through SQLAlchemy metadata.

- [ ] **Step 4: Implement project registration and response envelopes**

~~~python
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    team_identifier: str | None = Field(default=None, max_length=120)
    repository_root: str
    remote_url: str | None = None
    default_branch: str = "main"


class ApiEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ApiError | None = None
~~~

Use an idempotency_keys row keyed by endpoint plus Idempotency-Key. Return the original result for an identical replay and HTTP 409 when the same key carries a different request hash.

- [ ] **Step 5: Wire lifespan migrations and project routes**

Update create_app so lifespan opens Database, applies migrations, constructs ProjectService, and closes the engine. Health now returns database: "ok" after SELECT 1 and database: "error" with HTTP 503 when unavailable.

- [ ] **Step 6: Verify migration and API behavior**

Run:

~~~bash
uv run alembic -c backend/alembic.ini upgrade head
uv run pytest backend/tests/db backend/tests/projects -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: pragmas, migration, validation, idempotency, 404, and health tests pass.

- [ ] **Step 7: Commit project registration**

~~~bash
git add backend pyproject.toml
git commit -m "feat: add SQLite project registry"
~~~

---

### Task 3: Build Immutable Source Ingestion and Durable Jobs

**Files:**
- Create: backend/migrations/versions/0002_sources_jobs.py
- Create: backend/src/gpd/sources/schemas.py
- Create: backend/src/gpd/sources/repository.py
- Create: backend/src/gpd/sources/service.py
- Create: backend/src/gpd/sources/parsers.py
- Create: backend/src/gpd/sources/router.py
- Create: backend/src/gpd/jobs/models.py
- Create: backend/src/gpd/jobs/repository.py
- Create: backend/src/gpd/jobs/runner.py
- Create: backend/src/gpd/jobs/router.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/sources/test_source_ingestion.py
- Test: backend/tests/jobs/test_job_runner.py

**Interfaces:**
- Consumes: Database, Project
- Produces: Source {id, project_id, type, title, canonical_ref, author, captured_at, content_hash, raw_content, state}
- Produces: SourceSpan {id, source_id, locator, content, checksum}
- Produces: JobRunner.register(job_type: str, handler: JobHandler) -> None
- Produces: POST /api/v1/projects/{project_id}/sources, GET /sources/{source_id}, GET /jobs/{job_id}

- [ ] **Step 1: Write failing immutable-source and lease-recovery tests**

~~~python
def test_duplicate_content_reuses_immutable_source(client, project_id):
    body = {"type": "prd", "title": "Checkout PRD", "content": "# Checkout"}
    first = client.post(f"/api/v1/projects/{project_id}/sources", json=body)
    second = client.post(f"/api/v1/projects/{project_id}/sources", json=body)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["source_id"] == second.json()["data"]["source_id"]


def test_expired_job_lease_can_be_reclaimed(job_repository, clock):
    job = job_repository.enqueue("ingest_source", {"source_id": "source-1"}, "source-1:v1")
    claimed = job_repository.claim("worker-a", lease_seconds=30)
    clock.advance(seconds=31)

    reclaimed = job_repository.claim("worker-b", lease_seconds=30)
    assert reclaimed.id == job.id
    assert reclaimed.worker_id == "worker-b"
~~~

- [ ] **Step 2: Run tests and confirm source/job modules are missing**

Run: uv run pytest backend/tests/sources backend/tests/jobs -q

Expected: collection or route failures.

- [ ] **Step 3: Add source, span, chunk, and job schema**

Create sources, source_spans, knowledge_items, knowledge_evidence, knowledge_chunks, jobs, and job_attempts. Enforce unique (project_id, content_hash, type), unique job idempotency_key, and allowed state checks.

Job states are queued, running, succeeded, failed, and cancelled. Source states are queued, parsing, indexing, ready, embedding_pending, and failed.

- [ ] **Step 4: Implement safe Markdown ingestion**

~~~python
@dataclass(frozen=True)
class ParsedChunk:
    locator: str
    text: str
    token_estimate: int


def parse_markdown(content: str, max_chunk_chars: int = 4_000) -> list[ParsedChunk]:
    headings = split_on_markdown_headings(content)
    return [
        ParsedChunk(locator=section.locator, text=piece, token_estimate=max(1, len(piece) // 4))
        for section in headings
        for piece in split_long_text(section.text, max_chunk_chars)
        if piece.strip()
    ]
~~~

The API accepts uploaded text, not arbitrary backend filesystem paths. The CLI reads a user-selected file within the registered repository and sends content plus repository-relative canonical_ref. Normalize UTF-8, reject NUL bytes, cap sources at 2 MiB, and hash normalized content with SHA-256.

- [ ] **Step 5: Implement durable job execution**

~~~python
class JobHandler(Protocol):
    async def __call__(self, payload: dict[str, Any]) -> None: ...


class JobRunner:
    def register(self, job_type: str, handler: JobHandler) -> None: ...
    async def run_once(self, worker_id: str) -> bool: ...
    async def run_forever(self, worker_id: str, stop: asyncio.Event) -> None: ...
~~~

Persist the job before returning HTTP 202. Claim with a transaction, renew leases during long work, use bounded exponential backoff for retryable errors, and return expired leases to queued state at startup.

- [ ] **Step 6: Verify ingestion, job recovery, and error states**

Run:

~~~bash
uv run pytest backend/tests/sources backend/tests/jobs -q
uv run alembic -c backend/alembic.ini upgrade head
uv run ruff check backend
~~~

Expected: deduplication, immutable content, chunk locators, progress, retry, lease recovery, cancellation, and size/encoding tests pass.

- [ ] **Step 7: Commit ingestion and jobs**

~~~bash
git add backend
git commit -m "feat: ingest immutable project sources"
~~~

---

### Task 4: Add FTS5, sqlite-vec, and Deterministic Hybrid Retrieval

**Files:**
- Create: backend/migrations/versions/0003_search_indexes.py
- Create: backend/src/gpd/knowledge/embeddings.py
- Create: backend/src/gpd/knowledge/search.py
- Create: backend/src/gpd/knowledge/scoring.py
- Create: backend/src/gpd/knowledge/indexer.py
- Create: backend/src/gpd/knowledge/router.py
- Modify: backend/src/gpd/jobs/runner.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/knowledge/test_fts_search.py
- Test: backend/tests/knowledge/test_hybrid_search.py
- Test: backend/tests/knowledge/test_degraded_search.py

**Interfaces:**
- Consumes: Source chunks and durable jobs
- Produces: EmbeddingProvider.embed(texts: Sequence[str]) -> list[list[float]]
- Produces: SearchIndex.index(chunks), lexical(query, limit), vector(vector, limit), health()
- Produces: HybridSearchService.search(SearchQuery) -> SearchResult with hits and warnings
- Produces: GET /api/v1/projects/{project_id}/search?q=...&limit=...

- [ ] **Step 1: Write failing rank-fusion and degraded-mode tests**

~~~python
def test_hybrid_search_rewards_direct_task_links(hybrid_search):
    result = hybrid_search.search(
        SearchQuery(
            project_id="p1",
            text="expired payment method",
            task_id="task-1",
            related_files=["src/payment/service.ts"],
            limit=5,
        )
    )
    assert result.hits[0].chunk_id == "directly-linked"
    assert "direct_task_link" in result.hits[0].selection_reasons


def test_fts_fallback_returns_warning_when_vectors_unavailable(search_without_vec):
    result = search_without_vec.search(SearchQuery(project_id="p1", text="payment invalid"))
    assert result.hits
    assert result.warnings == ["vector_search_unavailable"]
~~~

- [ ] **Step 2: Run focused search tests**

Run: uv run pytest backend/tests/knowledge -q

Expected: missing search interfaces and indexes.

- [ ] **Step 3: Create lexical and vector indexes**

The migration creates an FTS5 external-content table keyed to knowledge_chunks, synchronization triggers for insert/update/delete, and a vec0 virtual table with one float embedding column at the configured dimension. Loading sqlite-vec is attempted per database connection; failure marks vector health unavailable without blocking migration or FTS5.

- [ ] **Step 4: Implement embedding and search adapters**

~~~python
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SearchIndex(Protocol):
    def index_chunks(self, chunks: Sequence[IndexedChunk]) -> None: ...
    def lexical(self, project_id: str, query: str, limit: int) -> list[RankedChunk]: ...
    def vector(self, project_id: str, vector: Sequence[float], limit: int) -> list[RankedChunk]: ...
    def health(self) -> SearchHealth: ...
~~~

Reject non-finite vectors and dimension mismatches. Store embedding provider, model, dimension, and content hash so model changes can enqueue re-embedding.

- [ ] **Step 5: Implement reciprocal-rank fusion and domain boosts**

~~~python
def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


BOOSTS = {
    "direct_task_link": 0.40,
    "exact_file_link": 0.30,
    "same_component": 0.20,
    "confirmed_knowledge": 0.15,
    "source_conversation": 0.10,
}
~~~

Return component scores and human-readable selection reasons with every hit. Never let an LLM override mandatory direct relationships or unresolved high-severity warnings.

- [ ] **Step 6: Verify search in full and degraded modes**

Run:

~~~bash
uv run pytest backend/tests/knowledge -q
uv run pytest backend/tests/sources -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: FTS ranking, vector ranking, fusion, filters, boosts, dimension validation, pending embeddings, and FTS-only fallback pass.

- [ ] **Step 7: Commit hybrid retrieval**

~~~bash
git add backend pyproject.toml
git commit -m "feat: add SQLite hybrid context search"
~~~

---

### Task 5: Add Conversations, Tasks, and Evidence-Backed Bug Extraction

**Files:**
- Create: backend/migrations/versions/0004_conversations_tasks.py
- Create: backend/src/gpd/conversations/schemas.py
- Create: backend/src/gpd/conversations/repository.py
- Create: backend/src/gpd/conversations/service.py
- Create: backend/src/gpd/tasks/schemas.py
- Create: backend/src/gpd/tasks/repository.py
- Create: backend/src/gpd/tasks/service.py
- Create: backend/src/gpd/tasks/router.py
- Create: backend/src/gpd/llm/gateway.py
- Create: backend/src/gpd/llm/workflows/bug_extraction.py
- Create: backend/src/gpd/llm/recording.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/tasks/test_task_api.py
- Test: backend/tests/llm/test_bug_extraction.py

**Interfaces:**
- Consumes: Source, SourceSpan, JobRunner
- Produces: LlmGateway.generate_structured(request, output_type) -> T
- Produces: BugExtraction with per-field EvidenceRef and confidence
- Produces: Task and BugDetails records with public IDs BUG-1, BUG-2
- Produces: POST /api/v1/conversations/{conversation_id}/bugs
- Produces: GET /api/v1/tasks and GET /api/v1/tasks/{task_ref}, resolving either internal UUID or public BUG-N identifier

- [ ] **Step 1: Write failing extraction validation tests**

~~~python
async def test_bug_extraction_keeps_unknown_environment_empty(fake_llm, bug_workflow, thread):
    fake_llm.respond(
        {
            "title": {"value": "Checkout hangs on expired card", "confidence": 0.98, "evidence": ["m1"]},
            "description": {"value": "Loading never ends after the API error.", "confidence": 0.95, "evidence": ["m1", "m3"]},
            "actual_behavior": {"value": "API returns payment_method_invalid and UI keeps loading.", "confidence": 0.99, "evidence": ["m2", "m3"]},
            "expected_behavior": {"value": "Show an error and allow another method.", "confidence": 0.94, "evidence": ["m4"]},
            "environment": {"value": None, "confidence": 0.0, "evidence": []},
        }
    )
    extraction = await bug_workflow.extract(thread)
    assert extraction.environment.value is None


async def test_bug_extraction_rejects_evidence_outside_thread(fake_llm, bug_workflow, thread):
    fake_llm.respond(valid_bug_payload(title_evidence=["not-in-thread"]))
    with pytest.raises(InvalidEvidenceReference):
        await bug_workflow.extract(thread)
~~~

- [ ] **Step 2: Run task and LLM tests**

Run: uv run pytest backend/tests/tasks backend/tests/llm -q

Expected: missing task and workflow modules.

- [ ] **Step 3: Migrate normalized conversations and tasks**

Create conversations, conversation_messages, tasks, bug_details, task_sources, task_knowledge, task_files, llm_runs, and public_id_counters. Enforce ordered unique external message IDs per conversation, one bug_details row per bug task, and source/evidence foreign keys.

- [ ] **Step 4: Implement versioned structured LLM workflow**

~~~python
class EvidenceRef(BaseModel):
    message_id: str


class ExtractedField(BaseModel, Generic[T]):
    value: T | None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceRef]


class BugExtraction(BaseModel):
    title: ExtractedField[str]
    description: ExtractedField[str]
    reproduction_steps: ExtractedField[list[str]]
    actual_behavior: ExtractedField[str]
    expected_behavior: ExtractedField[str]
    environment: ExtractedField[str]
    severity: ExtractedField[Literal["low", "medium", "high", "critical"]]
    affected_component: ExtractedField[str]
    technical_clues: ExtractedField[list[str]]
~~~

The workflow requires nonempty title and description, validates every evidence message ID against the input thread, and performs one corrective retry after schema failure. Store workflow name, prompt version, schema version, model, token counts, source IDs, state, and sanitized validation error.

- [ ] **Step 5: Implement atomic bug creation**

~~~python
class TaskService:
    async def create_bug_from_conversation(
        self,
        conversation_id: UUID,
        idempotency_key: str,
    ) -> TaskDetail:
        extraction = await self.bug_workflow.extract(
            self.conversations.require(conversation_id)
        )
        return self.repository.create_bug_with_evidence(
            conversation_id=conversation_id,
            extraction=extraction,
            idempotency_key=idempotency_key,
        )
~~~

Allocate the next public BUG-N identifier in the same write transaction as task, bug details, task-source link, field evidence, and audit event.

- [ ] **Step 6: Verify task behavior and provider-free recordings**

Run:

~~~bash
uv run pytest backend/tests/tasks backend/tests/llm -q
uv run alembic -c backend/alembic.ini upgrade head
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: public IDs, validation, evidence retention, unknown fields, idempotency, corrective retry, provider errors, and list/detail routes pass using fake recordings.

- [ ] **Step 7: Commit conversation-to-bug domain**

~~~bash
git add backend fixtures/llm
git commit -m "feat: extract evidence-backed bugs"
~~~

---

### Task 6: Connect the Slack Thread Workflow

**Files:**
- Create: backend/src/gpd/integrations/slack/signatures.py
- Create: backend/src/gpd/integrations/slack/client.py
- Create: backend/src/gpd/integrations/slack/parser.py
- Create: backend/src/gpd/integrations/slack/service.py
- Create: backend/src/gpd/integrations/slack/router.py
- Modify: backend/src/gpd/settings.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/slack/test_signatures.py
- Test: backend/tests/slack/test_event_workflow.py
- Create: fixtures/slack/checkout_bug_thread.json

**Interfaces:**
- Consumes: TaskService.create_bug_from_conversation
- Produces: SlackClient.fetch_thread(channel_id, thread_ts) -> SlackThread
- Produces: POST /api/v1/integrations/slack/events
- Produces: Slack invocation parser supporting “create a bug” and “create a bug task”

- [ ] **Step 1: Write failing signature, replay, and deduplication tests**

~~~python
def test_valid_slack_signature_is_accepted(slack_client, signed_checkout_event):
    response = slack_client.post(
        "/api/v1/integrations/slack/events",
        content=signed_checkout_event.body,
        headers=signed_checkout_event.headers,
    )
    assert response.status_code == 200


def test_old_slack_timestamp_is_rejected(slack_client, old_signed_event):
    response = slack_client.post(
        "/api/v1/integrations/slack/events",
        content=old_signed_event.body,
        headers=old_signed_event.headers,
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "slack_replay_rejected"
~~~

- [ ] **Step 2: Run Slack tests**

Run: uv run pytest backend/tests/slack -q

Expected: missing signature and event route failures.

- [ ] **Step 3: Implement signing verification before JSON parsing**

~~~python
def verify_slack_signature(
    signing_secret: SecretStr,
    timestamp: str,
    raw_body: bytes,
    signature: str,
    now: datetime,
) -> None:
    if abs(now.timestamp() - int(timestamp)) > 300:
        raise SlackReplayRejected()
    base = b"v0:" + timestamp.encode() + b":" + raw_body
    expected = "v0=" + hmac.new(
        signing_secret.get_secret_value().encode(), base, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SlackSignatureInvalid()
~~~

Do not log the raw signed body. Handle Slack URL verification synchronously; persist all other accepted events with external event ID as the idempotency key and acknowledge within three seconds.

- [ ] **Step 4: Implement thread normalization and invocation handling**

Normalize bot/user identities, timestamps, links, and message order into ConversationMessage. Ignore bot retries and messages without a supported GPD mention. Fetch the parent plus all replies, store the immutable source, create the normalized conversation, enqueue bug extraction, then post a success or reviewable failure message.

~~~python
SUPPORTED_BUG_PHRASES = (
    "create a bug",
    "create bug",
    "create a bug task",
)
~~~

The Slack success response includes public task ID, title, actual behavior, expected behavior, affected component, source-link confirmation, unknown-field warning, and dashboard URL.

- [ ] **Step 5: Verify the recorded Slack workflow**

Run:

~~~bash
uv run pytest backend/tests/slack backend/tests/tasks -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: URL verification, signatures, replay window, event retries, pagination, supported invocation, unsupported text, thread persistence, one bug per event, and response formatting pass without live Slack access.

- [ ] **Step 6: Commit Slack integration**

~~~bash
git add backend fixtures/slack
git commit -m "feat: create bugs from Slack threads"
~~~

---

### Task 7: Track Developer Sessions, Git State, and Work Overlap

**Files:**
- Create: backend/migrations/versions/0005_sessions_conflicts.py
- Create: backend/src/gpd/sessions/schemas.py
- Create: backend/src/gpd/sessions/git_inspector.py
- Create: backend/src/gpd/sessions/repository.py
- Create: backend/src/gpd/sessions/service.py
- Create: backend/src/gpd/sessions/router.py
- Create: backend/src/gpd/conflicts/overlap.py
- Create: backend/src/gpd/conflicts/repository.py
- Create: backend/src/gpd/conflicts/router.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/sessions/test_git_inspector.py
- Test: backend/tests/sessions/test_session_api.py
- Test: backend/tests/conflicts/test_overlap.py

**Interfaces:**
- Consumes: Repository, Task
- Produces: GitSnapshot {root, branch, changed_files, recent_commits, remote_url}
- Produces: SessionService.start(StartSession) -> DeveloperSession
- Produces: POST /api/v1/sessions, POST /sessions/{id}/heartbeat, GET /sessions
- Produces: Conflict type work_overlap with severity, explanation, and evidence
- Produces: OverlapWarning {severity, explanation, suggested_action, evidence}

- [ ] **Step 1: Write failing Git parsing and overlap tests**

~~~python
def test_git_inspector_returns_repository_relative_changes(git_repo):
    (git_repo / "src/payment/service.ts").write_text("changed")
    snapshot = GitInspector().inspect(git_repo)
    assert snapshot.branch == "feature/payment"
    assert snapshot.changed_files == [
        ChangedFile(path="src/payment/service.ts", change_kind="modified")
    ]


def test_same_file_in_active_sessions_is_high_overlap(overlap_detector):
    conflict = overlap_detector.compare(
        session(task="BUG-1", files=["src/payment/service.ts"]),
        session(task="TASK-2", files=["src/payment/service.ts"]),
    )
    assert conflict.severity == "high"
    assert conflict.evidence[0].kind == "exact_file"
~~~

- [ ] **Step 2: Run session and conflict tests**

Run: uv run pytest backend/tests/sessions backend/tests/conflicts/test_overlap.py -q

Expected: missing GitInspector and session services.

- [ ] **Step 3: Migrate session and conflict records**

Create developer_sessions, session_files, session_commits, conflicts, conflict_evidence, and audit records. Session states are active, stale, analyzing, completed, and abandoned. An active heartbeat expires after a configurable 120 seconds.

- [ ] **Step 4: Implement safe Git inspection**

~~~python
class GitInspector:
    def inspect(self, repository_root: Path) -> GitSnapshot:
        root = self._run(repository_root, ["rev-parse", "--show-toplevel"]).strip()
        branch = self._run(repository_root, ["branch", "--show-current"]).strip()
        status = self._run(repository_root, ["status", "--porcelain=v1", "-z"])
        commits = self._run(
            repository_root,
            ["log", "-5", "--format=%H%x00%s%x00%aI%x00"],
        )
        return parse_snapshot(root, branch, status, commits)
~~~

Execute with subprocess argument arrays, shell=False, a five-second timeout, sanitized environment, and a repository-root allowlist. Never read changed file contents in session tracking.

- [ ] **Step 5: Implement sessions and overlap warnings**

On session start, validate project, task, and registered repository; capture a Git snapshot; persist changed files; compare with fresh active sessions; and return warnings. Heartbeats replace the session’s current file observation set and update last_seen_at.

Overlap weights are exact file 1.0, same module 0.6, same component 0.5, same or explicitly related task 0.4, and shared confirmed knowledge 0.2. Severity is high at 1.0, medium at 0.6, and low at 0.4. Store the component scores. Return suggested_action with a concrete coordination recommendation: avoid an exact overlapping file until the named session completes, coordinate before editing the shared module, or continue when overlap is informational.

- [ ] **Step 6: Verify session lifecycle**

Run:

~~~bash
uv run pytest backend/tests/sessions backend/tests/conflicts/test_overlap.py -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: Git timeouts, detached branch, renamed/deleted files, active/stale transitions, heartbeats, exact-file and module overlap, no false same-file warning for stale sessions, and evidence persistence pass.

- [ ] **Step 7: Commit developer coordination**

~~~bash
git add backend
git commit -m "feat: track active developer work"
~~~

---

### Task 8: Assemble Stored, Budgeted Context Packages

**Files:**
- Create: backend/migrations/versions/0006_context_packages.py
- Create: backend/src/gpd/context/schemas.py
- Create: backend/src/gpd/context/query_builder.py
- Create: backend/src/gpd/context/budget.py
- Create: backend/src/gpd/context/assembler.py
- Create: backend/src/gpd/context/renderers.py
- Create: backend/src/gpd/context/repository.py
- Create: backend/src/gpd/context/router.py
- Modify: backend/src/gpd/sessions/service.py
- Modify: backend/src/gpd/app.py
- Test: backend/tests/context/test_assembler.py
- Test: backend/tests/context/test_renderers.py

**Interfaces:**
- Consumes: TaskDetail, HybridSearchService, active conflicts, confirmed knowledge
- Produces: ContextAssembler.assemble(ContextRequest) -> ContextPackage
- Produces: GET /api/v1/sessions/{session_id}/context?format=json|text
- Produces: immutable ContextPackage and ordered ContextEntry with score explanation

- [ ] **Step 1: Write failing mandatory-fact and token-budget tests**

~~~python
def test_context_keeps_task_facts_and_high_conflicts_under_budget(assembler):
    package = assembler.assemble(
        ContextRequest(session_id="s1", developer_prompt="fix the loading state", token_budget=900)
    )
    sections = [entry.section for entry in package.entries]
    assert sections[:2] == ["task", "expected_actual"]
    assert "high_severity_conflicts" in sections
    assert package.estimated_tokens <= 900


def test_text_and_json_renderers_share_entry_order(context_package):
    text = TextContextRenderer().render(context_package)
    payload = JsonContextRenderer().render(context_package)
    assert [entry.id for entry in payload["entries"]] == context_package.entry_ids
    assert text.index("TASK") < text.index("ORIGINAL DISCUSSION")
~~~

- [ ] **Step 2: Run context tests**

Run: uv run pytest backend/tests/context -q

Expected: missing context package and assembler.

- [ ] **Step 3: Migrate context package persistence**

Create context_packages and context_entries. Store session, task, developer query, budget, renderer version, search-health snapshot, warning codes, selected entry content, score components, selection reason, rank, and token estimate. Packages are immutable snapshots.

- [ ] **Step 4: Implement query construction and deterministic budgeting**

~~~python
MANDATORY_SECTIONS = (
    "task",
    "expected_actual",
    "high_severity_conflicts",
)


class TokenBudget:
    def select(
        self,
        mandatory: Sequence[CandidateEntry],
        optional: Sequence[CandidateEntry],
        limit: int,
    ) -> list[CandidateEntry]:
        selected = list(mandatory)
        remaining = limit - sum(item.token_estimate for item in selected)
        for item in diversify(optional):
            if item.token_estimate <= remaining:
                selected.append(item)
                remaining -= item.token_estimate
        return selected
~~~

If mandatory facts exceed the requested budget, compact their presentation without dropping title, actual behavior, expected behavior, or high-severity warnings; record budget_exceeded_by_mandatory warning.

- [ ] **Step 5: Implement assembly and renderers**

Order sections as task, expected/actual, original discussion, confirmed requirements/decisions, related files, active-work warnings, contradictory context, and background. JSON includes full scoring details; text contains compact headings, provenance labels, and warning banners. Creating a package stores the exact selected content so later index changes do not rewrite history.

- [ ] **Step 6: Verify complete and degraded packages**

Run:

~~~bash
uv run pytest backend/tests/context backend/tests/knowledge backend/tests/conflicts -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: deterministic ordering, diversity, budget enforcement, provenance, immutable snapshots, conflict inclusion, empty optional results, and vector-unavailable warnings pass.

- [ ] **Step 7: Commit context assembly**

~~~bash
git add backend
git commit -m "feat: assemble coding context packages"
~~~

---

### Task 9: Implement the Developer CLI and External-Agent Launcher

**Files:**
- Create: packages/contracts/package.json
- Create: packages/contracts/src/index.ts
- Create: packages/config/package.json
- Create: packages/config/src/project-config.ts
- Create: packages/api-client/package.json
- Create: packages/api-client/src/client.ts
- Create: apps/cli/package.json
- Create: apps/cli/src/main.ts
- Create: apps/cli/src/output.ts
- Create: apps/cli/src/git.ts
- Create: apps/cli/src/agent-launcher.ts
- Create: apps/cli/src/commands/init.ts
- Create: apps/cli/src/commands/add.ts
- Create: apps/cli/src/commands/task.ts
- Create: apps/cli/src/commands/session.ts
- Create: apps/cli/src/commands/context.ts
- Create: apps/cli/src/commands/agent.ts
- Create: apps/cli/src/commands/knowledge.ts
- Create: apps/cli/src/commands/doctor.ts
- Test: packages/config/src/project-config.test.ts
- Test: packages/api-client/src/client.test.ts
- Test: apps/cli/src/commands/cli.test.ts
- Test: apps/cli/src/agent-launcher.test.ts

**Interfaces:**
- Consumes: /api/v1 project, source, task, session, context, knowledge, and health endpoints
- Produces: GpdConfig {apiUrl, projectId, repositoryId, currentTaskId}
- Produces: gpd init, server start, add, task list/show/set, start, status, context, agent, finish, knowledge review, doctor
- Produces: AgentLauncher.launch(command: string[], contextPath: string, prompt: string) -> Promise<number>

- [ ] **Step 1: Write failing config-discovery and command-envelope tests**

~~~typescript
it("finds .gpd/config.json from a nested directory", async () => {
  const config = await findProjectConfig("/repo/src/payment");
  expect(config.path).toBe("/repo/.gpd/config.json");
  expect(config.value.projectId).toBe("project-1");
});

it("prints the stable JSON envelope", async () => {
  const result = await runCli(["status", "--json"], fakeRuntime());
  expect(JSON.parse(result.stdout)).toEqual({
    ok: true,
    data: expect.objectContaining({ session: null }),
    warnings: [],
    error: null,
  });
});
~~~

- [ ] **Step 2: Run TypeScript tests**

Run: pnpm --filter @gpd/cli test

Expected: workspace packages and runCli are missing.

- [ ] **Step 3: Implement contracts, configuration, and API client**

~~~typescript
export type ApiEnvelope<T> = {
  ok: boolean;
  data: T | null;
  warnings: string[];
  error: { code: string; message: string; retryable: boolean; fields?: Record<string, string> } | null;
};

export type GpdConfig = {
  apiUrl: string;
  projectId: string;
  repositoryId: string;
  currentTaskId: string | null;
};
~~~

ApiClient applies a request timeout, sends an Idempotency-Key for mutations, parses ApiEnvelope, and maps backend error codes to stable CLI exit codes: 2 validation, 3 configuration, 4 unavailable, 5 conflict, and 1 unexpected.

- [ ] **Step 4: Implement server, project, ingestion, task, and session commands**

Use Commander command modules with injected filesystem, process, clock, and ApiClient dependencies. gpd server start launches uv run uvicorn gpd.app:app with an argument array, supports foreground and --detach, and polls /health/ready with a bounded timeout. gpd init detects the Git root, remote, and default branch; registers through the API; and atomically writes .gpd/config.json. gpd add reads only the explicit path, verifies it is within the Git root, caps input at 2 MiB, and sends source content. gpd task list/show render backend pagination/detail, gpd task set validates the task then atomically updates currentTaskId, gpd start sends Git metadata and creates the session, and gpd status shows the selected task plus session and search health.

- [ ] **Step 5: Implement context, finish, knowledge review, and doctor**

gpd context defaults to text and supports --format json. gpd finish sends changed-file metadata, commit summaries, and an optional summary without embedding full source files. gpd knowledge review lists proposals and supports confirm, edit, and reject subcommands. gpd doctor checks config parsing, backend reachability, database/search health, Git availability, registered root, Slack configuration, and LLM configuration.

- [ ] **Step 6: Implement safe external-agent launching**

~~~typescript
export async function launchAgent(input: {
  command: string[];
  contextText: string;
  prompt: string;
  spawn: typeof nodeSpawn;
}): Promise<number> {
  const directory = await mkdtemp(join(tmpdir(), "gpd-context-"));
  const contextPath = join(directory, "context.md");
  await writeFile(contextPath, input.contextText, { mode: 0o600 });
  const child = input.spawn(input.command[0], [
    ...input.command.slice(1),
    "--gpd-context",
    contextPath,
    input.prompt,
  ], { shell: false, stdio: "inherit" });
  return await waitForExitAndRemove(directory, child);
}
~~~

Agent adapters define their supported context argument or stdin contract in configuration. Never concatenate a shell command. Remove temporary files after exit and on SIGINT/SIGTERM.

The gpd agent command starts a session when none is active, fetches and stores the canonical context package, launches the configured adapter, sends bounded heartbeats while the child runs, preserves the child exit code, and leaves knowledge extraction to the explicit gpd finish command.

- [ ] **Step 7: Verify the entire CLI**

Run:

~~~bash
pnpm --filter @gpd/config test
pnpm --filter @gpd/api-client test
pnpm --filter @gpd/cli test
pnpm --filter @gpd/cli typecheck
pnpm --filter @gpd/cli lint
~~~

Expected: nested config discovery, atomic writes, path safety, every command, JSON output, error exits, request timeout, agent argument safety, temporary-file permissions, and cleanup tests pass.

- [ ] **Step 8: Commit the CLI**

~~~bash
git add apps/cli packages package.json pnpm-workspace.yaml pnpm-lock.yaml
git commit -m "feat: add the GPD developer CLI"
~~~

---

### Task 10: Expose Agent-Neutral MCP Tools

**Files:**
- Create: apps/mcp/package.json
- Create: apps/mcp/src/server.ts
- Create: apps/mcp/src/runtime.ts
- Create: apps/mcp/src/tools/project.ts
- Create: apps/mcp/src/tools/tasks.ts
- Create: apps/mcp/src/tools/sessions.ts
- Create: apps/mcp/src/tools/context.ts
- Create: apps/mcp/src/tools/knowledge.ts
- Test: apps/mcp/src/server.test.ts
- Test: apps/mcp/src/tools/tools.test.ts
- Modify: README.md

**Interfaces:**
- Consumes: @gpd/api-client, @gpd/config, @gpd/contracts
- Produces: stdio MCP server with the eleven approved gpd_* tools
- Produces: structuredContent plus concise text and warning annotations

- [ ] **Step 1: Write failing tool registration and mapping tests**

~~~typescript
it("registers the stable GPD tool names", async () => {
  const server = createGpdMcpServer(fakeApiClient());
  expect(server.registeredToolNames()).toEqual([
    "gpd_project_get",
    "gpd_task_list",
    "gpd_task_get",
    "gpd_task_select",
    "gpd_session_start",
    "gpd_session_status",
    "gpd_context_get",
    "gpd_activity_report",
    "gpd_session_finish",
    "gpd_knowledge_proposal_list",
    "gpd_knowledge_proposal_confirm",
  ]);
});

it("returns retrieval warnings to the agent", async () => {
  const result = await callTool("gpd_context_get", { sessionId: "s1" });
  expect(result.structuredContent.warnings).toContain("vector_search_unavailable");
});
~~~

- [ ] **Step 2: Run MCP tests**

Run: pnpm --filter @gpd/mcp test

Expected: missing MCP server and tools.

- [ ] **Step 3: Implement server startup and schema validation**

Use the MCP TypeScript SDK stdio transport. Load .gpd/config.json from the MCP process working directory or GPD_CONFIG_PATH. Validate every input with Zod before calling ApiClient. Write protocol messages only to stdout and diagnostics only to stderr.

- [ ] **Step 4: Implement read tools**

gpd_project_get returns the project and search/integration health. gpd_task_list accepts status, type, assignee, query, and cursor. gpd_task_get includes bug detail and provenance. gpd_session_status returns Git/session freshness. gpd_context_get returns the stored canonical package. gpd_knowledge_proposal_list returns pending proposals with evidence.

- [ ] **Step 5: Implement mutation tools**

gpd_task_select validates and writes currentTaskId atomically. gpd_session_start and gpd_session_finish send idempotency keys. gpd_activity_report updates heartbeat and relative changed files. gpd_knowledge_proposal_confirm requires proposal ID and optional edited title/content, and returns the confirmed knowledge item.

- [ ] **Step 6: Verify MCP protocol behavior**

Run:

~~~bash
pnpm --filter @gpd/mcp test
pnpm --filter @gpd/mcp typecheck
pnpm --filter @gpd/mcp lint
~~~

Expected: schemas, configuration errors, backend failures, warnings, text plus structured output, no stdout logging, and all tool mappings pass.

- [ ] **Step 7: Commit MCP integration**

~~~bash
git add apps/mcp README.md pnpm-lock.yaml
git commit -m "feat: expose GPD context over MCP"
~~~

---

### Task 11: Detect and Resolve Contradictory Project Knowledge

**Files:**
- Create: backend/src/gpd/conflicts/schemas.py
- Create: backend/src/gpd/conflicts/candidates.py
- Create: backend/src/gpd/conflicts/contradictions.py
- Create: backend/src/gpd/llm/workflows/contradiction.py
- Modify: backend/src/gpd/conflicts/router.py
- Modify: backend/src/gpd/knowledge/indexer.py
- Test: backend/tests/conflicts/test_contradictions.py
- Test: backend/tests/conflicts/test_resolution.py

**Interfaces:**
- Consumes: confirmed knowledge, source evidence, LlmGateway
- Produces: ContradictionResult {classification, confidence, explanation, evidence_ids}
- Produces: POST /api/v1/conflicts/scan, GET /conflicts, POST /conflicts/{id}/resolve
- Produces: resolution actions supersede, clarify_scope, accept_conditional, dismiss

- [ ] **Step 1: Write failing contradiction and resolution tests**

~~~python
def test_retry_policy_conflict_keeps_both_sources(detector):
    conflict = detector.detect(
        claim("Retry payment three times", evidence="prd:12"),
        claim("Retries were reduced to one", evidence="slack:m4"),
    )
    assert conflict.classification == "contradictory"
    assert set(conflict.evidence_ids) == {"prd:12", "slack:m4"}


def test_supersede_resolution_does_not_delete_old_claim(conflict_service):
    resolved = conflict_service.resolve("c1", action="supersede", winner_id="k2")
    assert resolved.status == "resolved"
    assert conflict_service.knowledge("k1").status == "superseded"
    assert conflict_service.knowledge("k1").evidence
~~~

- [ ] **Step 2: Run conflict tests**

Run: uv run pytest backend/tests/conflicts -q

Expected: contradiction workflow and resolution actions are missing.

- [ ] **Step 3: Implement deterministic candidate grouping**

Generate candidates only within the same project and compatible knowledge types. Use normalized subject tags, related task/component/file, direct relationships, and hybrid-search neighbors. Exclude identical content hashes and already-resolved pairs.

- [ ] **Step 4: Implement the constrained contradiction workflow**

~~~python
class ContradictionResult(BaseModel):
    classification: Literal["compatible", "superseding", "ambiguous", "contradictory"]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[UUID] = Field(min_length=2)
~~~

Validate returned evidence against the candidate pair. Create a conflict only for ambiguous or contradictory results above 0.70 confidence; lower scores remain scan diagnostics. Store detector and prompt versions.

- [ ] **Step 5: Implement explicit conflict resolution**

Require actor and resolution note. supersede marks the losing knowledge item superseded; clarify_scope and accept_conditional create a confirmed clarifying item linked to both claims; dismiss retains the detector result but excludes the pair from repeated scans. Append an audit event in the same transaction.

- [ ] **Step 6: Verify detection and resolution**

Run:

~~~bash
uv run pytest backend/tests/conflicts backend/tests/context -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: candidate grouping, supported classifications, evidence validation, confidence threshold, duplicate scan suppression, each resolution action, audit history, and context warning inclusion pass.

- [ ] **Step 7: Commit knowledge conflicts**

~~~bash
git add backend
git commit -m "feat: detect project knowledge conflicts"
~~~

---

### Task 12: Finish Sessions and Promote Reviewed Knowledge

**Files:**
- Create: backend/migrations/versions/0007_knowledge_proposals.py
- Create: backend/src/gpd/knowledge/proposals.py
- Create: backend/src/gpd/knowledge/service.py
- Create: backend/src/gpd/llm/workflows/knowledge_extraction.py
- Create: backend/src/gpd/sessions/completion.py
- Modify: backend/src/gpd/sessions/service.py
- Modify: backend/src/gpd/sessions/router.py
- Modify: backend/src/gpd/knowledge/router.py
- Test: backend/tests/sessions/test_completion.py
- Test: backend/tests/knowledge/test_proposals.py
- Test: backend/tests/knowledge/test_memory_reuse.py

**Interfaces:**
- Consumes: task, stored context package, final Git snapshot, commit summaries, optional agent summary
- Produces: KnowledgeProposal {id, type, title, content, confidence, evidence, status}
- Produces: POST /api/v1/sessions/{id}/finish
- Produces: GET /api/v1/knowledge/proposals and POST /proposals/{id}/confirm|edit|reject
- Produces: confirmed KnowledgeItem eligible for indexing and future context

- [ ] **Step 1: Write failing approval-gate and reuse tests**

~~~python
def test_finish_creates_proposals_not_confirmed_knowledge(completion_service, session):
    result = completion_service.finish(session.id, agent_summary="Normalized payment error.")
    assert result.session.status == "analyzing"
    assert result.job.type == "extract_knowledge"
    assert completion_service.confirmed_knowledge(session.id) == []


def test_confirmed_proposal_is_retrieved_for_later_related_task(
    proposal_service, context_assembler, payment_proposal
):
    item = proposal_service.confirm(payment_proposal.id, actor="alice")
    package = context_assembler.assemble(later_payment_task_request())
    assert item.id in [entry.knowledge_id for entry in package.entries]
~~~

- [ ] **Step 2: Run completion and knowledge tests**

Run: uv run pytest backend/tests/sessions/test_completion.py backend/tests/knowledge/test_proposals.py backend/tests/knowledge/test_memory_reuse.py -q

Expected: missing completion and proposal services.

- [ ] **Step 3: Migrate proposals and confirmation history**

Create knowledge_proposals and proposal_evidence. Proposal states are pending, confirmed, edited_and_confirmed, and rejected. Store source session, extraction workflow version, proposed fields, confidence, actor, decision time, and evidence references.

- [ ] **Step 4: Implement sanitized completion input**

~~~python
class CompletionInput(BaseModel):
    task_id: UUID
    context_package_id: UUID
    changed_files: list[ChangedFile]
    diff_summary: str = Field(max_length=20_000)
    commits: list[CommitSummary]
    agent_summary: str | None = Field(default=None, max_length=10_000)
~~~

Git diff summarization records file names, change counts, and redacted bounded hunks. Exclude binary content, files matching secret patterns, and content outside the registered repository. Store a checksum of the inspected Git state.

- [ ] **Step 5: Implement evidence-backed knowledge extraction**

The workflow may propose decision, architecture_rule, implementation_constraint, technical_discovery, or task_context. Each proposal needs nonempty title/content, confidence, and at least one evidence reference to task, context entry, commit, changed file, or agent summary. Invalid references reject the workflow output.

- [ ] **Step 6: Implement human decisions and reindexing**

Confirm creates a new confirmed KnowledgeItem plus evidence and enqueues indexing. Edit-and-confirm stores both proposed and accepted content. Reject records actor and reason without creating knowledge. Every decision is idempotent and audited. Trigger contradiction scanning after confirmation.

- [ ] **Step 7: Verify the learn-and-reuse loop**

Run:

~~~bash
uv run pytest backend/tests/sessions backend/tests/knowledge backend/tests/context -q
uv run ruff check backend
uv run mypy backend/src
~~~

Expected: finish idempotency, safe diff input, job progress, invalid evidence rejection, all review decisions, audit records, indexing, contradiction scan, and later context reuse pass.

- [ ] **Step 8: Commit reviewed memory capture**

~~~bash
git add backend
git commit -m "feat: capture reviewed implementation knowledge"
~~~

---

### Task 13: Build the Dashboard Shell, Overview, and Task Experience

**Files:**
- Create: apps/web/package.json
- Create: apps/web/vite.config.ts
- Create: apps/web/index.html
- Create: apps/web/src/main.tsx
- Create: apps/web/src/app/router.tsx
- Create: apps/web/src/app/providers.tsx
- Create: apps/web/src/styles/tokens.css
- Create: apps/web/src/styles/global.css
- Create: apps/web/src/components/AppShell.tsx
- Create: apps/web/src/components/AsyncState.tsx
- Create: apps/web/src/components/ProvenanceLink.tsx
- Create: apps/web/src/components/WarningBanner.tsx
- Create: apps/web/src/pages/OverviewPage.tsx
- Create: apps/web/src/pages/TasksPage.tsx
- Create: apps/web/src/pages/TaskDetailPage.tsx
- Create: apps/web/src/features/tasks/api.ts
- Create: apps/web/src/features/tasks/TaskFacts.tsx
- Create: apps/web/src/features/tasks/ContextPreview.tsx
- Test: apps/web/src/pages/TasksPage.test.tsx
- Test: apps/web/src/pages/TaskDetailPage.test.tsx
- Test: apps/web/src/components/AsyncState.test.tsx

**Interfaces:**
- Consumes: @gpd/api-client and backend task/context/session/conflict endpoints
- Produces: accessible responsive application shell
- Produces: overview, task list, task detail, source provenance, and context preview

- [ ] **Step 1: Write failing loading, empty, provenance, and degraded-state tests**

~~~tsx
it("shows unknown bug fields without inventing values", async () => {
  renderApp("/tasks/BUG-1", apiWithTask({ environment: null }));
  expect(await screen.findByRole("heading", { name: "Checkout hangs on expired card" })).toBeVisible();
  expect(screen.getByText("Environment")).toBeVisible();
  expect(screen.getByText("Unknown")).toBeVisible();
});

it("shows context provenance and vector fallback", async () => {
  renderApp("/tasks/BUG-1", apiWithContext({ warnings: ["vector_search_unavailable"] }));
  expect(await screen.findByText("Semantic search unavailable; using keyword search.")).toBeVisible();
  expect(screen.getByRole("link", { name: /Slack message/ })).toBeVisible();
});
~~~

- [ ] **Step 2: Run web tests**

Run: pnpm --filter @gpd/web test

Expected: web package and components are missing.

- [ ] **Step 3: Implement the design foundation**

Define CSS tokens for canvas, surface, text, muted text, borders, focus, success, warning, danger, spacing, radius, and type scale. Use semantic HTML, visible focus, 44-pixel minimum interactive targets, reduced-motion support, and WCAG AA contrast. AppShell provides primary navigation, project identity, backend/search health, and a narrow-screen drawer.

- [ ] **Step 4: Implement overview and task list**

Overview queries active sessions, recent tasks, unresolved conflicts, job failures, and system health. TasksPage supports query, status, type, assignee, component, and cursor pagination; filters are URL state. Provide skeleton, empty, error, stale, and retry states.

- [ ] **Step 5: Implement task detail and context preview**

TaskDetailPage displays title, status, priority, reporter/assignee, reproduction, actual, expected, environment, severity, component, clues, linked files, original sources, related knowledge, active sessions, conflicts, and context package preview. Unknown fields visibly say Unknown. Each extracted fact links to evidence and displays confidence only when below the configured trust threshold.

- [ ] **Step 6: Verify dashboard foundation**

Run:

~~~bash
pnpm --filter @gpd/web test
pnpm --filter @gpd/web typecheck
pnpm --filter @gpd/web lint
pnpm --filter @gpd/web build
~~~

Expected: navigation, accessibility queries, responsive shell, all async states, filters, source links, unknown fields, conflicts, degraded search, and production build pass.

- [ ] **Step 7: Commit dashboard tasks**

~~~bash
git add apps/web packages pnpm-lock.yaml
git commit -m "feat: add GPD task dashboard"
~~~

---

### Task 14: Complete Knowledge, Sources, Sessions, Conflicts, Jobs, and Settings UI

**Files:**
- Create: backend/src/gpd/projects/settings_router.py
- Create: backend/tests/projects/test_settings_api.py
- Create: apps/web/src/pages/KnowledgePage.tsx
- Create: apps/web/src/pages/KnowledgeReviewPage.tsx
- Create: apps/web/src/pages/SourcesPage.tsx
- Create: apps/web/src/pages/SourceDetailPage.tsx
- Create: apps/web/src/pages/SessionsPage.tsx
- Create: apps/web/src/pages/ConflictsPage.tsx
- Create: apps/web/src/pages/ConflictDetailPage.tsx
- Create: apps/web/src/pages/JobsPage.tsx
- Create: apps/web/src/pages/SettingsPage.tsx
- Create: apps/web/src/features/knowledge/api.ts
- Create: apps/web/src/features/sources/api.ts
- Create: apps/web/src/features/sessions/api.ts
- Create: apps/web/src/features/conflicts/api.ts
- Create: apps/web/src/features/jobs/api.ts
- Create: apps/web/src/features/settings/api.ts
- Modify: apps/web/src/app/router.tsx
- Modify: apps/web/src/components/AppShell.tsx
- Test: apps/web/src/pages/KnowledgeReviewPage.test.tsx
- Test: apps/web/src/pages/ConflictDetailPage.test.tsx
- Test: apps/web/src/pages/OperationsPages.test.tsx

**Interfaces:**
- Consumes: source, knowledge, proposal, session, conflict, job, integration, and health APIs
- Produces: complete review and operations experience
- Produces: GET and PATCH /api/v1/projects/{project_id}/settings with secret-presence booleans

- [ ] **Step 1: Write failing review and conflict-resolution tests**

~~~tsx
it("requires a deliberate action before promoting knowledge", async () => {
  renderApp("/knowledge/review", apiWithProposal());
  expect(await screen.findByText("Normalize payment_method_invalid in PaymentService")).toBeVisible();
  expect(screen.getByRole("button", { name: "Confirm knowledge" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
});

it("shows both claims before resolving a contradiction", async () => {
  renderApp("/conflicts/c1", apiWithRetryConflict());
  expect(await screen.findByText("Retry payment three times")).toBeVisible();
  expect(screen.getByText("Retries were reduced to one")).toBeVisible();
  expect(screen.getByLabelText("Resolution note")).toBeRequired();
});
~~~

- [ ] **Step 2: Run operational-page tests**

Run: pnpm --filter @gpd/web test -- KnowledgeReviewPage ConflictDetailPage OperationsPages

Expected: pages and routes are missing.

- [ ] **Step 3: Implement knowledge and source pages**

Knowledge supports type/status/source/component filters, hybrid query, provenance display, superseded relationships, and degraded-search warnings. Review supports confirm, edit-and-confirm, and reject with optimistic locking. Sources show immutable content, version links, spans, chunks, ingestion/indexing state, and retryable failures.

- [ ] **Step 4: Implement session and conflict pages**

Sessions show developer/agent, task, repository, branch, changed files, freshness, and overlap. Conflicts show type, severity, state, evidence comparison, score components, and audit trail. Resolution forms expose supersede, clarify scope, accept conditional, and dismiss; destructive-looking choices include plain-language impact before submit.

- [ ] **Step 5: Implement jobs and settings pages**

Add the project settings endpoints with optimistic version checks and an allowlist of editable non-secret fields. The response exposes slack_credential_configured and llm_credential_configured booleans, never secret values. Jobs show progress, attempts, error code, retryability, retry, and queued-job cancellation. Settings edit non-secret project/repository values, display whether Slack and LLM credentials are configured, set model names and context budget, and show database/FTS/vector health.

- [ ] **Step 6: Verify all dashboard states**

Run:

~~~bash
pnpm --filter @gpd/web test
pnpm --filter @gpd/web typecheck
pnpm --filter @gpd/web lint
pnpm --filter @gpd/web build
~~~

Expected: review gates, concurrent edit handling, immutable sources, stale sessions, conflict resolution, failed-job recovery, hidden secrets, keyboard use, and responsive layouts pass.

- [ ] **Step 7: Commit the complete dashboard**

~~~bash
git add apps/web
git commit -m "feat: complete GPD operations dashboard"
~~~

---

### Task 15: Harden Security, Backup, Health, and Local Deployment

**Files:**
- Create: backend/src/gpd/security/redaction.py
- Create: backend/src/gpd/security/auth.py
- Create: backend/src/gpd/audit/service.py
- Create: backend/src/gpd/db/backup.py
- Create: backend/src/gpd/api/routers/health.py
- Create: backend/src/gpd/api/routers/admin.py
- Create: compose.yaml
- Create: Dockerfile
- Modify: backend/src/gpd/settings.py
- Modify: backend/src/gpd/app.py
- Modify: .env.example
- Modify: README.md
- Test: backend/tests/security/test_redaction.py
- Test: backend/tests/security/test_non_loopback_auth.py
- Test: backend/tests/db/test_backup.py
- Test: backend/tests/api/test_health.py

**Interfaces:**
- Produces: Redactor.redact(text: str) -> RedactionResult
- Produces: POST /api/v1/admin/backup -> backup path and checksum
- Produces: GET /health/live and GET /health/ready
- Produces: explicit bearer token requirement when binding outside loopback

- [ ] **Step 1: Write failing security and backup tests**

~~~python
def test_redactor_removes_common_secret_formats(redactor):
    result = redactor.redact("token=sk-example1234567890 and xoxb-123-456-secret")
    assert "sk-example" not in result.text
    assert "xoxb-" not in result.text
    assert result.redaction_count == 2


def test_non_loopback_binding_requires_access_token():
    with pytest.raises(SettingsError, match="access token"):
        Settings(api_host="0.0.0.0", access_token=None)


def test_online_backup_is_integrity_checked(database, backup_service, tmp_path):
    result = backup_service.create(tmp_path / "backup.db")
    assert result.integrity_check == "ok"
    assert result.sha256
~~~

- [ ] **Step 2: Run hardening tests**

Run: uv run pytest backend/tests/security backend/tests/db/test_backup.py backend/tests/api/test_health.py -q

Expected: redactor, binding validation, backup service, and split health routes are missing.

- [ ] **Step 3: Implement redaction and local access control**

Redact configured regexes plus OpenAI-style keys, Slack tokens, GitHub tokens, PEM private-key blocks, Authorization headers, and dotenv secret assignments before LLM calls and audit/error persistence. If api_host is not loopback, startup requires GPD_ACCESS_TOKEN; protect /api/v1 with constant-time bearer-token comparison while leaving liveness free of internal detail.

- [ ] **Step 4: Implement health, integrity, and online backup**

Liveness reports only process state. Readiness checks migration head, SELECT 1, PRAGMA integrity_check, FTS5 query, vector extension health, job worker lease, and configured integrations; optional/degraded checks become warnings, while database or migration failure returns 503. Backup uses sqlite3.Connection.backup into an explicit .gpd/backups path, runs integrity_check on the result, and returns SHA-256.

- [ ] **Step 5: Add reproducible local deployment**

Use one multi-stage Dockerfile: a Node stage builds apps/web, a Python stage installs the locked backend, and the final non-root image copies the web assets for FastAPI to serve with history fallback outside /api. compose.yaml defines one gpd service, a named volume mounted at /data, GPD_DATABASE_PATH=/data/gpd.db, health checks, a loopback published port, and no Redis/Postgres service. The job runner starts in the FastAPI lifespan with a distinct worker identity and graceful shutdown.

- [ ] **Step 6: Verify native and container operations**

Run:

~~~bash
uv run pytest backend/tests -q
pnpm -r test
docker compose config
docker compose build
docker compose up -d
curl --fail http://127.0.0.1:7337/health/ready
docker compose down
~~~

Expected: all tests pass, configuration renders, images build, readiness succeeds, and shutdown preserves the SQLite volume.

- [ ] **Step 7: Commit operational hardening**

~~~bash
git add .
git commit -m "feat: harden local GPD deployment"
~~~

---

### Task 16: Add the Deterministic Demo and End-to-End Release Gate

**Files:**
- Create: fixtures/demo-project/docs/checkout-prd.md
- Create: fixtures/demo-project/docs/payment-adr.md
- Create: fixtures/demo-project/src/payment/payment-service.ts
- Create: fixtures/demo-project/src/checkout/payment-errors.ts
- Create: fixtures/llm/bug-extraction-checkout.json
- Create: fixtures/llm/knowledge-extraction-payment.json
- Create: tests/e2e/fake_slack_server.py
- Create: tests/e2e/fake_llm_server.py
- Create: tests/e2e/test_demo_flow.py
- Create: apps/web/e2e/demo-flow.spec.ts
- Create: scripts/demo.sh
- Modify: README.md
- Modify: package.json

**Interfaces:**
- Consumes: complete backend, Slack adapter, dashboard, CLI, and MCP server
- Produces: one-command deterministic demo environment
- Produces: end-to-end acceptance evidence for the full product loop

- [ ] **Step 1: Write the failing API/CLI/MCP demo test**

~~~python
def test_complete_project_memory_loop(demo):
    project = demo.gpd_init()
    demo.add("docs/checkout-prd.md")
    demo.add("docs/payment-adr.md")
    task = demo.post_signed_slack_fixture("checkout_bug_thread.json")
    assert task["public_id"] == "BUG-1"

    demo.cli("task set BUG-1")
    session = demo.cli("start").json()
    cli_context = demo.cli("context --format json").json()
    mcp_context = demo.mcp("gpd_context_get", {"sessionId": session["id"]})
    assert cli_context["data"]["entry_ids"] == mcp_context["entry_ids"]

    overlap = demo.start_overlapping_session("src/payment/payment-service.ts")
    assert "work_overlap" in overlap["warnings"]

    proposal = demo.finish_with_fixture_diff(session["id"])
    confirmed = demo.confirm_proposal(proposal["id"])
    later = demo.context_for_later_payment_task()
    assert confirmed["id"] in later["knowledge_ids"]
~~~

- [ ] **Step 2: Run the end-to-end test and confirm it fails before fixtures exist**

Run: uv run pytest tests/e2e/test_demo_flow.py -q

Expected: fixture and demo harness errors.

- [ ] **Step 3: Add deterministic external-service fakes and fixtures**

The fake Slack server implements thread retrieval and message posting for the recorded checkout thread. The fake LLM server returns schema-valid recordings keyed by workflow name and prompt version, plus configurable transient and invalid-schema responses. Fixtures contain no real credentials or copied private conversations.

- [ ] **Step 4: Implement the full demo harness**

scripts/demo.sh creates a temporary demo workspace, starts backend/web/fakes on free ports, initializes GPD, ingests the two docs, submits the signed Slack event, waits for durable jobs, selects BUG-1, starts a session, retrieves CLI and MCP context, creates overlap, completes work with the fixture diff, confirms knowledge, verifies reuse, and prints dashboard URLs. A trap always stops processes and keeps the temporary database path for inspection when the run fails.

- [ ] **Step 5: Add browser acceptance coverage**

~~~typescript
test("judge can inspect the complete project-memory loop", async ({ page }) => {
  await page.goto("/tasks/BUG-1");
  await expect(page.getByRole("heading", { name: "Checkout hangs on expired card" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Slack message/ })).toBeVisible();
  await expect(page.getByText("payment_method_invalid")).toBeVisible();
  await page.getByRole("link", { name: "Knowledge review" }).click();
  await expect(page.getByText("Normalize payment errors in PaymentService")).toBeVisible();
});
~~~

- [ ] **Step 6: Verify vector-disabled fallback**

Run the demo with GPD_VECTOR_SEARCH_ENABLED=false. Assert that bug creation, task selection, FTS5 context, CLI, MCP, completion, review, and reuse still work and that vector_search_unavailable appears as a warning.

- [ ] **Step 7: Run the complete release gate**

Run:

~~~bash
uv run pytest backend/tests tests/e2e -q
uv run ruff check backend tests
uv run mypy backend/src
pnpm -r test
pnpm -r typecheck
pnpm -r lint
pnpm --filter @gpd/web build
pnpm --filter @gpd/web exec playwright test
GPD_VECTOR_SEARCH_ENABLED=false uv run pytest tests/e2e/test_demo_flow.py -q
docker compose config
docker compose build
~~~

Expected: every command exits 0; the complete loop passes with and without vector search.

- [ ] **Step 8: Document the judge-facing workflow**

README.md must contain prerequisites, native setup, Docker setup, Slack environment variables, LLM environment variables, gpd init/add/task/start/context/finish examples, MCP client configuration, demo command, backup/recovery, degraded-mode behavior, and known first-release boundaries.

- [ ] **Step 9: Commit the release gate**

~~~bash
git add .
git commit -m "test: add complete GPD demo flow"
~~~

---

## Final Verification

- [ ] Read docs/superpowers/specs/2026-09-12-gpd-architecture-design.md and map every included-scope bullet to at least one passing test or explicit release-gate assertion.
- [ ] Run git status --short and verify no generated databases, secrets, environment files, caches, temporary agent context, or build products are staged.
- [ ] Run the Task 16 release-gate commands from a fresh clone.
- [ ] Open the dashboard at desktop and narrow viewport widths and complete the Slack bug, task context, overlap, conflict, and knowledge-review flows using only visible controls.
- [ ] Inspect BUG-1 field evidence, the stored context package, a work-overlap conflict, a contradiction, and a confirmed knowledge item to verify provenance remains intact.
- [ ] Confirm the final commit history has independently reviewable commits matching Tasks 1–16.
