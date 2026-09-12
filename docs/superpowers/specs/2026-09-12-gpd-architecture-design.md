# GPD Local Platform Architecture Design

**Date:** 2026-09-12  
**Status:** Approved design  
**Source requirements:** `docs/GPD — Product Requirements Document.md` and `docs/GPD — Functional Requirements Document.md`

## 1. Purpose

GPD is a local-first shared memory and coordination layer for software teams working with humans and coding agents. It turns project conversations and documents into durable, traceable knowledge; creates structured work from those sources; gives coding agents a compact context package; tracks active work; identifies important conflicts; and captures reusable knowledge after implementation.

The first release must demonstrate the complete loop:

```text
Slack discussion
  -> structured bug
  -> durable project memory
  -> selected developer task
  -> coding-agent context
  -> active-work coordination
  -> completed implementation
  -> reviewed knowledge update
  -> reusable future context
```

The system includes a backend server, browser interface, developer CLI, and agent-neutral MCP server. It runs on one developer machine or a team-accessible local host without managed cloud infrastructure.

## 2. Scope

### 2.1 Included in the first release

- Local project registration and repository association.
- Markdown, PRD, FRD, ADR, task, Slack-thread, and manual-note ingestion.
- Slack app installation, signed event handling, thread retrieval, natural-language invocation, and result posting.
- Structured bug creation from a Slack thread with source provenance and confidence.
- Persistent project memory in SQLite.
- Hybrid lexical and semantic context retrieval.
- Manual task selection and developer-session lifecycle.
- Git repository, branch, changed-file, and recent-commit detection.
- Compact, inspectable context packages for developers and coding agents.
- Agent-neutral MCP tools and a CLI wrapper for external coding agents.
- Active-work tracking and overlap warnings based on task, component, module, and file.
- Detection of important contradictions among project knowledge.
- Post-task knowledge extraction, human confirmation, and future reuse.
- Browser dashboard for tasks, knowledge, sources, sessions, conflicts, jobs, and settings.
- Deterministic demo fixtures and an end-to-end checkout-bug demonstration.

### 2.2 Deferred from the first release

- Jira, Linear, GitHub issue creation, and Microsoft Teams integration.
- Automatic task inference from branch names or prompts.
- Advanced permissions, enterprise identity, and tenant isolation.
- Cloud synchronization, high availability, and horizontal scaling.
- A built-in coding agent or code editor.
- Multiple messaging adapters beyond Slack.

These items are outside the first implementation plan. The internal ports and adapter boundaries must allow later additions without shaping the first release around them.

## 3. Product Principles

1. **Context follows the work.** A task carries its sources and relevant knowledge across Slack, the dashboard, terminal, and coding agent.
2. **Provenance is mandatory.** Generated claims retain links to source records and, where possible, source spans.
3. **Unknown remains unknown.** Missing or low-confidence facts are never silently invented.
4. **Relevance beats volume.** Context packages are selected and budgeted, not raw knowledge dumps.
5. **Humans approve durable learning.** Completion analysis produces proposals; it does not silently rewrite project memory.
6. **One local database is enough.** SQLite stores operational data, search indexes, embeddings, job state, and audit history.
7. **Interfaces share one domain model.** Browser, CLI, MCP, and Slack use versioned backend APIs rather than duplicating business rules.

## 4. Technology Baseline

- Python 3.12 or newer for the backend, worker, domain services, Git inspection, retrieval, and LLM workflows.
- FastAPI with Pydantic v2 for HTTP APIs and validated domain/LLM contracts.
- SQLAlchemy 2 and Alembic for SQLite access and schema migrations.
- SQLite 3 with WAL mode, FTS5, foreign keys, and periodic integrity checks.
- `sqlite-vec` for local vector similarity search, behind a search adapter.
- React and TypeScript for the browser interface.
- Node.js 24 or newer with pnpm workspaces for the CLI, MCP server, shared API client, and frontend toolchain.
- An MCP TypeScript SDK for the stdio MCP server.
- A provider-neutral Python LLM gateway with OpenAI as the initial configured provider.
- Docker Compose for a reproducible local stack; native development commands remain supported.
- Pytest for Python tests, Vitest and React Testing Library for TypeScript tests, and Playwright for browser workflows.

Dependency versions are locked in committed Python and pnpm lockfiles. The implementation may raise version floors but must not lower them below this baseline.

## 5. System Architecture

```text
                           +-------------------+
 Slack Events ------------> Slack HTTP Adapter |
                           +---------+---------+
                                     |
 Browser UI ----+                     v
 CLI -----------+--------------> FastAPI Application
 MCP Server ----+                     |
 External Agent +                     +-----------------------------+
                                     |             |               |
                              Domain Services   Job Runner     LLM Gateway
                                     |             |               |
                                     +-------------+---------------+
                                                   |
                                            SQLite + FTS5
                                                   |
                                             sqlite-vec
```

### 5.1 Deployment model

The normal installation is one FastAPI process, one colocated background job runner, one SQLite database file, and static frontend assets. The CLI and MCP server are separate local processes that communicate with FastAPI over loopback HTTP. Slack requires a reachable callback URL; local development may use a user-configured tunnel, but tunnel management is not a GPD responsibility.

The initial system is single-project-per-database and small-team oriented. The schema includes project identifiers so a later release can host multiple projects, but cross-tenant security is not claimed.

### 5.2 Backend module boundaries

The Python application is divided by business capability:

- **projects:** project identity, repository configuration, and integration settings.
- **sources:** immutable source records, source content, provenance spans, and ingestion state.
- **knowledge:** normalized knowledge items, chunks, relationships, confidence, lifecycle, and confirmation.
- **tasks:** generic task aggregate plus bug-specific fields and source relationships.
- **conversations:** normalized conversation messages and participants.
- **context:** candidate discovery, scoring, conflict annotations, budgeting, and package rendering.
- **sessions:** current task, Git snapshot, agent identity, heartbeat, completion, and active-file observations.
- **conflicts:** active-work overlap and contradictory-knowledge detection and resolution.
- **integrations/slack:** signature verification, event deduplication, thread retrieval, invocation parsing, and responses.
- **llm:** provider gateway, versioned workflow prompts, structured-output validation, token accounting, and redaction.
- **jobs:** durable asynchronous work, retry policy, cancellation, progress, and failure reporting.
- **audit:** records for artifact creation, knowledge confirmation, conflict resolution, and configuration changes.

Modules expose application-service interfaces. Route handlers translate transport data and call those services; they do not contain domain rules.

### 5.3 TypeScript workspace boundaries

- **apps/web:** React dashboard.
- **apps/cli:** human-facing `gpd` commands and external-agent launcher.
- **apps/mcp:** stdio MCP server.
- **packages/api-client:** generated or schema-checked client for backend `/api/v1` contracts.
- **packages/contracts:** TypeScript transport types, command result envelopes, and shared formatting primitives.
- **packages/config:** `.gpd/config.json` parsing and backend discovery.

The CLI and MCP server have no direct SQLite access. They remain thin clients with presentation, process-launching, and protocol responsibilities.

## 6. Persistence Design

### 6.1 Database location and ownership

By default, `gpd init` creates `.gpd/config.json` in the repository and configures the backend database at `.gpd/gpd.db`. The FastAPI process is the only database owner. Repository-relative paths are stored in domain records; absolute paths may be stored only in local configuration.

SQLite is configured with:

- WAL journal mode.
- Foreign keys enabled on every connection.
- A busy timeout for short write contention.
- One application-level write queue for jobs and request mutations.
- Short transactions with no network or LLM calls inside a transaction.
- Schema migrations applied explicitly on startup or through a management command.

### 6.2 Core records

- `projects`: identity, name, team label, timestamps.
- `repositories`: project, local path, remote URL, default branch.
- `integrations`: project, adapter type, non-secret configuration, enabled state.
- `sources`: type, title, canonical reference, author, capture time, immutable raw content hash, ingestion state.
- `source_spans`: source, locator, quoted or normalized span, checksum.
- `conversations`: source, external thread reference, channel metadata.
- `conversation_messages`: conversation, external message reference, author, timestamp, text, ordering.
- `knowledge_items`: type, title, normalized content, status, confidence, valid time, created time.
- `knowledge_evidence`: knowledge item, source span, support relationship.
- `knowledge_chunks`: knowledge item or source, text, token estimate, metadata.
- `tasks`: public identifier, type, title, description, status, priority, reporter, assignee, component, timestamps.
- `bug_details`: task, reproduction steps, expected behavior, actual behavior, environment, severity, technical clues.
- `task_sources`, `task_knowledge`, and `task_files`: explicit task relationships.
- `developer_sessions`: task, developer, repository, branch, agent, status, start/end/heartbeat timestamps.
- `session_files`: session, relative path, change kind, observation time.
- `context_packages`: task, session, query, budget, renderer version, creation time.
- `context_entries`: package, source or knowledge reference, score components, rank, selection reason, rendered content.
- `conflicts`: type, severity, status, explanation, detector version, timestamps.
- `conflict_evidence`: conflict, referenced task/session/knowledge/source/file.
- `knowledge_proposals`: session, proposed type/title/content, confidence, status, evidence.
- `jobs`: type, state, idempotency key, progress, attempts, error category, timestamps.
- `llm_runs`: workflow, provider, model, prompt/schema version, source references, token counts, state, validation errors.
- `audit_events`: actor, action, target, sanitized metadata, timestamp.

Credentials and API keys are excluded from the database. They are resolved from environment variables or the operating-system credential store.

### 6.3 Source and derived-data lifecycle

Raw sources are immutable. A corrected source is a new version linked to the earlier source. Knowledge items, tasks, chunks, embeddings, and context packages are derived records whose generator version is retained. Re-ingestion replaces derived search rows transactionally without deleting audit history or task provenance.

## 7. Search and Context Selection

### 7.1 Hybrid search

Every searchable chunk is indexed in SQLite FTS5. When an embedding provider and `sqlite-vec` are available, the same chunk also receives a fixed-dimension embedding row. Retrieval proceeds in five stages:

1. Build a query from the selected task, developer prompt, component, related files, and repository state.
2. Retrieve lexical candidates with FTS5 BM25 and semantic candidates with vector distance.
3. Merge candidate ranks with reciprocal-rank fusion.
4. Apply deterministic boosts and penalties for direct source links, task links, file/component overlap, source type, confirmation state, confidence, recency, and conflicts.
5. Select a diverse set under a configurable token budget and retain per-entry scoring explanations.

The default context ordering is task facts, expected/actual behavior, original conversation, confirmed requirements and decisions, related files, active-work warnings, conflicting context, and secondary background.

### 7.2 Degraded modes

- If embedding generation fails, ingestion succeeds with an explicit `embedding_pending` state.
- If `sqlite-vec` cannot load, retrieval uses FTS5 and deterministic relationships only.
- If the LLM reranker is unavailable, deterministic hybrid scores remain authoritative.
- If both vector and lexical search are unavailable, direct task/source/file relationships still produce a minimal context package.

The API, dashboard, CLI, and MCP responses expose degraded-state warnings without hiding otherwise usable results.

### 7.3 Search abstraction

The backend owns a `SearchIndex` interface for indexing, deleting, lexical lookup, vector lookup, and health checks. `SqliteHybridSearchIndex` is the first implementation. This boundary permits migration from `sqlite-vec` to SQLite Vec1 or another local extension without changing context-selection services.

## 8. LLM Workflows

### 8.1 Shared rules

Every workflow has:

- a stable workflow name and versioned prompt;
- a Pydantic input and output schema;
- explicit source identifiers;
- a defined confidence scale;
- structured validation errors;
- bounded retries for transient provider or schema failures;
- token and latency accounting;
- deterministic fallback behavior where the product can continue safely.

Prompt content and ingested text are untrusted data. LLM output cannot execute commands, change configuration, approve knowledge, or write directly to domain tables.

### 8.2 Conversation-to-bug extraction

Input is a normalized Slack thread and project metadata. Output includes title, summary, description, reproduction steps, actual behavior, expected behavior, environment, severity, affected component, technical clues, participants, confidence per field, and source-span references.

Required bug identity fields are title and description. Other missing fields remain null or empty. The system rejects source references outside the provided thread. The task and its source relationships are committed in one database transaction after validation.

### 8.3 Context query and reranking

An LLM may expand the retrieval query and rerank a bounded candidate list. Deterministic direct relationships and hard filters remain in force. The LLM cannot remove mandatory task facts, source provenance, unresolved high-severity conflicts, or active file-overlap warnings.

### 8.4 Contradictory-knowledge detection

Deterministic grouping first identifies candidates about the same subject. The LLM classifies whether their claims are compatible, superseding, ambiguous, or contradictory. A conflict is created only when at least two evidence records are retained. GPD displays all sides and does not silently select a winner.

### 8.5 Post-task knowledge extraction

Input includes the task, prior context package, sanitized Git diff summary, changed files, commit summaries, and optional coding-agent summary. Output is a list of evidence-backed knowledge proposals. A human must confirm, edit, or reject each proposal before it becomes confirmed project memory.

## 9. Core Workflows

### 9.1 Initialize a project

1. `gpd init` detects the Git repository, remote, current/default branch, and project name.
2. It writes `.gpd/config.json`, ensures `.gpd/gpd.db` is ignored by Git, and starts or discovers the backend.
3. It registers the project and repository through `/api/v1`.
4. It reports integration and search health and suggests `gpd add` for project documents.

### 9.2 Ingest project knowledge

1. A user runs `gpd add <path>` or submits a note through the dashboard.
2. The backend validates source type, path scope, encoding, and size.
3. It stores an immutable source and enqueues parsing, chunking, lexical indexing, embedding, and knowledge classification.
4. The user can inspect progress and failures from CLI or dashboard.

### 9.3 Create a bug from Slack

1. Slack sends an event to the signed webhook.
2. The adapter verifies the timestamp and signature, deduplicates the event, and acknowledges quickly.
3. A job retrieves and normalizes the complete thread.
4. The backend stores the conversation source and messages.
5. The extraction workflow produces a validated bug with evidence and confidence.
6. The task, bug details, and source links are committed atomically.
7. Slack receives the bug identifier, title, key facts, unknown-field warning when relevant, and dashboard link.

### 9.4 Start coding work and assemble context

1. `gpd task set BUG-231` validates the task through the backend, then stores its identifier in repository-local `.gpd/config.json`.
2. `gpd start` detects developer, repository, branch, changes, and recent commits and creates a session.
3. Context selection retrieves, scores, validates, budgets, and stores a context package.
4. GPD checks active session overlap and unresolved knowledge contradictions.
5. CLI output and MCP tools expose the same package and warnings.
6. Session heartbeats update active-file observations without uploading source-file contents unless the user explicitly ingests them.

### 9.5 Work through a coding agent

- An MCP-capable coding agent calls GPD tools to discover the project, select a task, start a session, retrieve context, report activity, and finish.
- `gpd agent "<prompt>"` supports non-MCP agents by rendering the canonical context and launching a configured external command. It passes context through a temporary file or supported process input rather than command-line interpolation.
- GPD never presents itself as the coding agent and never executes repository modifications on behalf of the external agent.

### 9.6 Finish and learn

1. `gpd finish` captures the final Git snapshot, changed-file list, diff summary, commit summaries, and optional agent summary.
2. The session becomes `analyzing`; the knowledge-extraction job runs outside the CLI request.
3. Proposed decisions, constraints, fixes, and technical discoveries appear in the dashboard and `gpd knowledge review`.
4. A human confirms, edits, or rejects proposals.
5. Confirmed knowledge is indexed and becomes eligible for future context packages.

## 10. Interface Design

### 10.1 Browser dashboard

- **Overview:** active sessions, recent tasks, unresolved conflicts, ingestion status, and degraded services.
- **Tasks:** list, filters, structured task detail, linked sources, knowledge, files, conflicts, and context preview.
- **Knowledge:** browse and search confirmed and proposed knowledge with provenance, confidence, and lifecycle.
- **Sources:** inspect Slack threads, documents, notes, versions, indexing state, and failures.
- **Sessions:** developer/agent, task, branch, files, heartbeat, conflicts, and completion state.
- **Conflicts:** evidence comparison, severity, resolution, dismissal, and audit history.
- **Jobs:** progress, retryable failures, attempts, and cancellation.
- **Settings:** project/repository settings, Slack configuration status, LLM and embedding model names, context budgets, retention, and health.

The interface is responsive, keyboard accessible, and usable without vector search. It never hides source provenance behind generated summaries.

### 10.2 CLI

The CLI supports human-readable output by default and JSON output for automation:

```text
gpd init
gpd server start
gpd add <path>
gpd task list
gpd task show <task-id>
gpd task set <task-id>
gpd start
gpd status
gpd context --format text|json
gpd agent "<prompt>"
gpd finish --summary <text>
gpd knowledge review
gpd doctor
```

Every mutation command supports idempotent retries. Failures use stable error codes and nonzero exit status. JSON output uses a common envelope containing `ok`, `data`, `warnings`, and `error`.

### 10.3 MCP server

The stdio MCP server exposes:

- `gpd_project_get`
- `gpd_task_list`
- `gpd_task_get`
- `gpd_task_select`
- `gpd_session_start`
- `gpd_session_status`
- `gpd_context_get`
- `gpd_activity_report`
- `gpd_session_finish`
- `gpd_knowledge_proposal_list`
- `gpd_knowledge_proposal_confirm`

Tool schemas are narrow and versioned. Responses contain structured data plus concise text suitable for agent consumption. Tools return explicit warnings for degraded retrieval, conflicts, stale sessions, or incomplete task facts.

### 10.4 HTTP API

All clients use `/api/v1`. Resources include projects, sources, ingestion jobs, conversations, tasks, sessions, context packages, conflicts, knowledge proposals, knowledge items, integrations, health, and audit events. Mutation endpoints accept idempotency keys. List endpoints use cursor pagination and stable filters. Error responses include a machine code, human message, retryability, and field details.

## 11. Active Work and Conflict Detection

### 11.1 Active-work overlap

Sessions are considered active while their heartbeat is fresh. Overlap scoring uses:

- exact relative-file matches;
- shared directory or module;
- shared task or related tasks;
- shared component;
- overlapping confirmed requirement or decision.

Exact same-file changes generate the strongest warning. Related-module warnings are advisory and display their evidence. GPD recommends coordination but does not block work.

### 11.2 Knowledge contradictions

Potential contradictions are detected during ingestion, task creation, context assembly, and knowledge confirmation. Each conflict retains the competing claims, evidence, detection method, confidence, and status. Resolution may mark one claim superseded, clarify scope, accept both under different conditions, or dismiss the detection. Resolution creates an audit event and a new knowledge relation; it does not erase source history.

## 12. Error Handling and Operations

### 12.1 Error categories

- Validation and unsupported input: not retried.
- Authentication and signature failures: rejected and audited without sensitive payloads.
- Transient LLM, Slack, or filesystem errors: retried with bounded exponential backoff.
- Structured-output validation failures: one corrective retry, then a reviewable failed job.
- Database contention: short retry within the configured busy timeout.
- Extension failure: switch to degraded lexical retrieval.
- Git inspection failure: create a session with explicit missing-environment warnings when safe.

### 12.2 Durable jobs

Jobs are persisted before execution. A worker claims jobs with a lease, renews long work, and records progress. Idempotency prevents duplicate Slack tasks and duplicate ingestion. Process restarts return expired leased jobs to the queue. Users may retry eligible failures or cancel queued work.

### 12.3 Backups and recovery

GPD provides a safe backup command using SQLite's online backup mechanism. Startup checks migration state and database integrity. Automatic destructive recovery is forbidden; corruption produces a diagnostic with the database and backup paths.

## 13. Security and Privacy

- Verify Slack signatures and reject events outside the replay window.
- Keep Slack, LLM, and other credentials out of SQLite and logs.
- Redact configured secret patterns before LLM submission and audit persistence.
- Restrict filesystem ingestion and Git inspection to registered repository roots and explicitly supplied files.
- Invoke Git and external agents with argument arrays, never shell interpolation.
- Enforce source size, message count, request body, context budget, and job runtime limits.
- Treat documents, conversations, repository text, and LLM output as untrusted content.
- Require explicit confirmation before durable knowledge promotion.
- Record security-relevant changes and artifact mutations in the audit log.
- Bind locally by default; non-loopback binding requires explicit configuration and an access token.

## 14. Testing Strategy

### 14.1 Python tests

- Unit tests for domain aggregates, state transitions, provenance validation, scoring, budgeting, overlap rules, contradiction classification, path safety, job leases, and Git parsing.
- Contract tests for each LLM workflow using recorded provider responses and invalid-output fixtures.
- Repository tests for migrations, SQLite constraints, WAL settings, FTS5, `sqlite-vec`, and degraded search.
- API integration tests with a fresh temporary SQLite database per test group.
- Slack tests for signature verification, replay rejection, deduplication, thread normalization, and response formatting.

### 14.2 TypeScript tests

- API client and contract tests against generated schemas.
- CLI parsing, configuration, output-envelope, exit-code, and process-launch safety tests.
- MCP tool-schema, backend mapping, warning, and error tests.
- React component tests for loading, empty, degraded, error, provenance, and conflict states.
- Playwright flows for task inspection, knowledge review, conflict resolution, job failure recovery, and settings health.

### 14.3 End-to-end acceptance tests

The release gate includes a scripted local scenario that:

1. Initializes a repository and ingests PRD, FRD, and ADR fixtures.
2. Posts a signed Slack checkout-bug fixture.
3. Verifies one evidence-backed bug and one preserved conversation.
4. Selects the bug and starts a developer session.
5. Retrieves the same context facts through CLI and MCP.
6. Starts a second overlapping session and verifies a warning.
7. Completes the first session with a fixture Git diff.
8. Reviews and confirms an extracted knowledge proposal.
9. Starts a later task and verifies that confirmed knowledge is reused.
10. Disables vector search and verifies a usable lexical fallback package.

Live LLM and Slack smoke tests are opt-in because normal CI must be deterministic and credential-free.

## 15. Delivery Decomposition

Implementation is divided into independently testable vertical milestones:

1. Workspace foundation, SQLite schema, backend health, and project initialization.
2. Source ingestion, immutable provenance, FTS5, embeddings, and hybrid retrieval.
3. Task and bug domain with manual/API creation and dashboard inspection.
4. Slack thread ingestion and conversation-to-bug workflow.
5. Developer sessions, Git detection, active-work tracking, and overlap warnings.
6. Context selection, package rendering, CLI workflow, and MCP tools.
7. Knowledge contradiction detection and resolution.
8. Task completion, knowledge proposals, confirmation, and memory reuse.
9. Complete dashboard, operational hardening, demo fixtures, and end-to-end release gate.

Each milestone must end with working software visible through at least one user-facing interface. The implementation plan will define test-first tasks and commits within these milestones.

## 16. Success Criteria

The first release is successful when:

- A natural Slack bug discussion becomes one structured bug without manual rewriting.
- Every important generated field can be traced to its source or marked as an inference.
- The original conversation remains linked and inspectable.
- A developer selects the bug and receives a compact context package without copying source text.
- The same canonical context is available through the CLI and MCP server.
- Active overlapping work and important contradictory knowledge are visible with evidence.
- Completion produces reviewable knowledge proposals, not silent memory mutations.
- Confirmed knowledge appears in a later relevant context package.
- The dashboard exposes the complete lifecycle and degraded states.
- The full demo runs locally with SQLite and remains usable when vector search or the LLM provider is temporarily unavailable.
