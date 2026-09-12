# GPD — Grounded Project Developer

GPD is a developer memory and team coordination platform that unifies project specifications (PRD, FRD, ADR), conversational discussions (Slack, Telegram), and active workspace state into budgeted, canonical context packages for human developers and external coding agents.

```
                  ┌─────────────────────────────────────────┐
                  │          External Interfaces            │
                  │  CLI (gpd)  •  Web UI  •  MCP  •  Chat  │
                  └────┬───────────┬─────────┬─────────┬────┘
                       │           │         │         │
                       ▼           ▼         ▼         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          GPD Monorepo                                  │
│                                                                        │
│  apps/cli        Developer command-line interface                      │
│  apps/web        React / Vite operations & knowledge review dashboard   │
│  apps/mcp        Model Context Protocol server for AI coding agents    │
│  apps/channel    Telegram bot agent for chat triage & proposals        │
│  backend         FastAPI, SQLite, FTS5 lexical search & vector index   │
│  packages/*      Shared api-client, config manager, and contracts      │
└────────────────────────────────────────────────────────────────────────┘
```

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

# Node workspace tests (api-client, config, contracts, cli, mcp, web, channel)
pnpm -r test
```

### Start Services

#### Option A: Individual Processes
```bash
# Terminal 1: Start GPD Backend API
uv run uvicorn gpd.app:app --host 127.0.0.1 --port 7337
# (or via CLI: gpd server start)

# Terminal 2: Start Web Dashboard
pnpm --filter @gpd/web dev

# Terminal 3: Start Telegram Bot Agent (optional)
pnpm dev:channel
# or: pnpm --filter @gpd/channel dev
```

#### Option B: Process Manager (PM2)
```bash
# Start API, Web Dashboard, and Telegram Channel simultaneously
pm2 start ecosystem.config.cjs
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
| `GPD_SESSION_HEARTBEAT_TIMEOUT_SECONDS` | `120` | Heartbeat inactivity timeout before marking active sessions stale |

### Slack Integration
| Variable | Description |
|---|---|
| `GPD_SLACK_SIGNING_SECRET` | HMAC-SHA256 signing secret for verifying incoming Slack event callbacks |
| `GPD_SLACK_BOT_TOKEN` | Bot user OAuth token (`xoxb-...`) for thread retrieval and confirmation messages |

### Telegram Bot Integration (@gpd/channel)
| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot user token from [@BotFather](https://t.me/BotFather) for Telegram assistant |
| `GPD_API_URL` | GPD backend API URL (e.g. `http://127.0.0.1:7337`) |
| `GPD_ACCESS_TOKEN` | Bearer token for authenticating channel agent requests to GPD API |

### LLM & Embedding Integration
| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *None* | OpenAI API key for extraction workflows and Telegram assistant |
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

# 3. List and inspect tasks
gpd task list
gpd task show BUG-1
gpd task set BUG-1

# 4. Start active developer session with Git context
gpd start

# 5. Assemble budgeted context package (text or JSON format)
gpd context
gpd context --format json

# 6. Check workspace, health, and diagnose system
gpd status
gpd doctor

# 7. Launch external coding agent with budgeted context (optional)
gpd agent "Fix payment timeout retry logic"

# 8. Complete session and extract new knowledge proposals
gpd finish --summary "Normalize payment errors in PaymentService"

# 9. Human review gate: review, confirm, edit, or reject knowledge proposals
gpd knowledge review
gpd knowledge review confirm <PROPOSAL_ID>
gpd knowledge review edit <PROPOSAL_ID> "Updated canonical knowledge content"
gpd knowledge review reject <PROPOSAL_ID> "Not applicable to main branch"
```

---
## 6. MCP Client Configuration

To integrate GPD with AI coding agents (such as Claude Desktop, Cursor, or Cline) via the Model Context Protocol (MCP):

For automatic discovery by MCP-enabled editors (Cursor, Claude Code), configure `.mcp.json` in your workspace root:
```json
{
  "mcpServers": {
    "gpd": {
      "command": "pnpm",
      "args": [
        "--filter",
        "@gpd/mcp",
        "exec",
        "tsx",
        "src/server.ts"
      ],
      "cwd": "/path/to/gpd",
      "env": {
        "GPD_API_URL": "http://127.0.0.1:7337",
        "GPD_ACCESS_TOKEN": ""
      }
    }
  }
}
```

Or when running from pre-built distribution:

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
- `gpd_project_get`: Retrieve current project metadata and subsystem health (database, search, integrations)
- `gpd_task_list`: Query and filter project tasks by status, type, and search query
- `gpd_task_get`: Fetch task details, acceptance criteria, bug reproduction steps, and source provenance
- `gpd_task_select`: Set active task and persist atomically to `.gpd/config.json`
- `gpd_session_start`: Start developer session with git snapshot and active-work conflict warnings
- `gpd_session_status`: Retrieve current session state, modified files, and active lease health
- `gpd_context_get`: Retrieve canonical budgeted context package for the active session
- `gpd_activity_report`: Report developer heartbeat, branch, and relative modified files
- `gpd_session_finish`: Complete session, submit commit/file metadata, and extract candidate knowledge proposals
- `gpd_knowledge_proposal_list`: List pending knowledge proposals with source evidence for review

*Note*: Knowledge proposals **cannot** be confirmed or modified via MCP tools. Confirmations are restricted to the CLI human gate (`gpd knowledge review confirm`) or the web dashboard.

---

## 7. Telegram Bot Agent (@gpd/channel)

GPD includes a Telegram bot assistant (`apps/channel`) built with [GrammY](https://grammy.dev/) that connects directly to the GPD API and OpenAI:

- **Direct Telegram Integration**: Connects directly to Telegram Bot API with long-polling — no external gateways or cloud proxies required.
- **Task Management**: Query tasks and triage bugs (`/tasks [status]`) or converse with the AI assistant.
- **Knowledge Search**: Search specifications, ADRs, and confirmed knowledge (`/search <query>`).
- **Human-in-the-Loop Decision Buttons**: Propose engineering actions (`/propose <action> | <details>`) with interactive inline keyboard buttons (`Approve` / `Hold`) for team review.
- **Structured Cards**: Rich formatting for task priorities, status badges, and source links.

### Telegram Commands
| Command | Description |
|---|---|
| `/start` | Display welcome greeting and bot capabilities |
| `/tasks [status]` | List project tasks and bugs (e.g. `/tasks open`) |
| `/search <query>` | Search knowledge base documents and specifications |
| `/propose <action> \| <details>` | Post an action proposal with interactive review buttons |
| `/help` | Display command help and usage examples |

---

## 8. Deterministic Demo & Release Gate Command

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

## 9. Backup & Disaster Recovery

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

## 10. Degraded Modes & Fallback Behavior

GPD is engineered to remain functional during external outages and misconfigurations:
- **Vector Search Unavailable (`vector_search_unavailable`)**: When `GPD_VECTOR_SEARCH_ENABLED=false` or SQLite vector extensions are disabled, GPD automatically falls back to SQLite FTS5 full-text lexical search and direct graph relationships. All core workflows remain green.
- **Lexical Search Unavailable (`lexical_search_unavailable`)**: If FTS5 indexes are unavailable, GPD falls back to direct task and source link relationships.
- **External Slack Outage**: Stored local fixtures provide fallback conversation threads when offline.
- **LLM Rate Limits / Transient Errors**: Automatic retries with exponential backoff prevent partial write corruption.

---

## 11. First-Release (v1) Boundaries

The initial release targets single-repository local developer workspaces:
- Single active project per local workspace directory (`.gpd/config.json`).
- Human confirmation gate is mandatory for knowledge promotion (external agents cannot self-promote knowledge).
- SQLite-backed local single-node architecture (distributed multi-node clustering planned for v2).
- Supported file types: Markdown (`.md`), TypeScript (`.ts`), JavaScript (`.js`), Python (`.py`), and JSON (`.json`).
