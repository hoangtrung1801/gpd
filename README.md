# GPD — Grounded Project Developer

GPD is a developer memory and team coordination platform that unifies project specifications (PRD, FRD, ADR), conversational discussions (Slack), and active workspace state into budgeted, canonical context packages for human developers and external coding agents.

---

## 1. Prerequisites
- **Node.js**: v20+ (Node v22+ recommended)
- **pnpm**: v9+ (or v11)
- **Python**: 3.11+ (with `uv` installed)
- **Git**: 2.38+
- **Docker & Docker Compose**: Optional for containerized deployment

---

## 2. Native Setup

### Install Dependencies
```bash
# Node workspace dependencies
pnpm install

# Python backend dependencies
uv sync
```

### Run Tests
```bash
# Python backend & E2E release gate tests
uv run pytest backend/tests tests/e2e -q

# Node workspace tests (api-client, config, contracts, cli, mcp, web)
pnpm -r test
```

### Start Services
```bash
# Terminal 1: Start GPD Backend API
uv run uvicorn gpd.app:app --host 127.0.0.1 --port 7337

# Terminal 2: Start Web Dashboard
pnpm --filter @gpd/web dev
```

---

## 3. Docker Setup

GPD can be launched in a single container with persistent data:

```bash
# Validate Docker Compose configuration
docker compose config

# Build and start GPD container
docker compose up -d

# Check service health
curl http://127.0.0.1:7337/health/live
```

---

## 4. Environment Variables

### Core Configuration
| Variable | Default | Description |
|---|---|---|
| `GPD_DATABASE_PATH` | `.gpd/gpd.db` | SQLite database file location |
| `GPD_API_HOST` | `127.0.0.1` | Host interface to bind API server |
| `GPD_API_PORT` | `7337` | Port for API server |
| `GPD_ACCESS_TOKEN` | *None* | Bearer token (required when binding non-loopback host) |
| `GPD_VECTOR_SEARCH_ENABLED` | `true` | Set `false` to disable vector embeddings and fallback to FTS5 |

### Slack Integration
| Variable | Description |
|---|---|
| `GPD_SLACK_SIGNING_SECRET` | HMAC-SHA256 signing secret for verifying incoming Slack event callbacks |
| `GPD_SLACK_BOT_TOKEN` | Bot user OAuth token (`xoxb-...`) for thread retrieval and confirmation messages |

### LLM & Embedding Integration
| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *None* | OpenAI API key for real extraction workflows (not required when using fakes) |
| `GPD_LLM_MODEL` | `gpt-4o` | Model name for structured extraction |
| `GPD_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for semantic vector index |
| `GPD_CONTEXT_TOKEN_BUDGET` | `8000` | Target token budget for assembled context packages |

---

## 5. CLI Workflow Examples

The GPD CLI (`gpd`) provides one-command developer workflow actions:

```bash
# 1. Initialize GPD in current repository
gpd init --api-url http://127.0.0.1:7337 --name my-project

# 2. Add specification and architecture documents
gpd add docs/checkout-prd.md
gpd add docs/checkout-frd.md
gpd add docs/payment-adr.md

# 3. List and select current task
gpd task list
gpd task set BUG-1

# 4. Start active developer session with Git context
gpd start

# 5. Assemble budgeted context package (text or JSON format)
gpd context
gpd context --format json

# 6. Check workspace and health status
gpd status

# 7. Complete session and extract new knowledge proposals
gpd finish --summary "Normalize payment errors in PaymentService"

# 8. Human review gate: review and confirm knowledge proposal via CLI
gpd knowledge review
gpd knowledge review confirm <PROPOSAL_ID>
```

---

## 6. MCP Client Configuration

To integrate GPD with AI coding agents (such as Claude Desktop, Cursor, or Cline) via the Model Context Protocol (MCP):

Add the following to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gpd": {
      "command": "node",
      "args": [
        "/path/to/gpd/apps/mcp/dist/server.js"
      ],
      "env": {
        "GPD_API_URL": "http://127.0.0.1:7337"
      }
    }
  }
}
```

### Exposed MCP Tools
- `gpd_project_get`: Retrieve current project metadata and settings
- `gpd_task_list`: Query and filter project tasks
- `gpd_task_get`: Fetch task details and evidence
- `gpd_task_select`: Set active task for current workspace
- `gpd_session_start`: Start developer session with git snapshot
- `gpd_session_status`: Retrieve current session and activity report
- `gpd_context_get`: Retrieve canonical budgeted context package
- `gpd_activity_report`: Report developer progress and edits
- `gpd_session_finish`: Complete session and trigger knowledge extraction
- `gpd_knowledge_proposal_list`: List pending knowledge proposals

*Note*: Knowledge proposals **cannot** be confirmed or modified via MCP tools. Confirmations are restricted to the CLI human gate (`gpd knowledge review confirm`) or the web dashboard.

---

## 7. Deterministic Demo & Release Gate Command

Run the complete deterministic demo harness in one command:

```bash
# Run via package.json script
pnpm demo

# Or run script directly
./scripts/demo.sh
```

The demo script automatically:
1. Creates an isolated temporary demo repository.
2. Starts deterministic external fakes (Fake Slack and Fake LLM).
3. Ingests PRD, FRD, and ADR specification documents.
4. Submits a signed Slack bug conversation event and extracts `BUG-1`.
5. Selects `BUG-1` and starts an active session.
6. Verifies CLI and MCP context package parity on `entry_ids`.
7. Detects active work overlap on conflicting files.
8. Finishes work with a diff, extracts a knowledge proposal, confirms it via CLI, and verifies reuse in later tasks.
9. Cleans up all background processes via trap handlers.

---

## 8. Backup & Disaster Recovery

GPD uses an atomic SQLite database with transaction logging:

### Automated Backup
```bash
# Create an online, lock-free SQLite backup
sqlite3 .gpd/gpd.db ".backup '.gpd/gpd-backup-$(date +%Y%m%d%H%M%S).db'"
```

### Recovery
```bash
# Restore from backup
cp .gpd/gpd-backup-<TIMESTAMP>.db .gpd/gpd.db
uv run python -m gpd.db.migrations
```

---

## 9. Degraded Modes & Fallback Behavior

GPD is engineered to remain functional during external outages and misconfigurations:
- **Vector Search Unavailable (`vector_search_unavailable`)**: When `GPD_VECTOR_SEARCH_ENABLED=false` or SQLite vector extensions are disabled, GPD automatically falls back to SQLite FTS5 full-text lexical search and direct graph relationships. All core workflows remain green.
- **Lexical Search Unavailable (`lexical_search_unavailable`)**: If FTS5 indexes are unavailable, GPD falls back to direct task and source link relationships.
- **External Slack Outage**: Stored local fixtures provide fallback conversation threads when offline.
- **LLM Rate Limits / Transient Errors**: Automatic retries with exponential backoff prevent partial write corruption.

---

## 10. First-Release (v1) Boundaries

The initial release targets single-repository local developer workspaces:
- Single active project per local workspace directory (`.gpd/config.json`).
- Human confirmation gate is mandatory for knowledge promotion (external agents cannot self-promote knowledge).
- SQLite-backed local single-node architecture (distributed multi-node clustering planned for v2).
- Supported file types: Markdown (`.md`), TypeScript (`.ts`), JavaScript (`.js`), Python (`.py`), and JSON (`.json`).
