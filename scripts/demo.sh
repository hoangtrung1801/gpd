#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# GPD Deterministic Demo & End-to-End Release Gate Harness
#
# Creates a temporary demo workspace, starts backend and deterministic fakes,
# initializes GPD, ingests 3 specification docs (PRD, FRD, ADR), submits signed
# Slack event to create BUG-1, selects task, starts developer session, retrieves
# budgeted context, demonstrates work overlap warning, finishes session with diff,
# reviews and confirms knowledge proposal via CLI, verifies memory reuse,
# and prints dashboard URLs.
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR=$(mktemp -d /tmp/gpd-demo-XXXXXX)
DEMO_DB="$DEMO_DIR/.gpd/gpd.db"
PIDS=()

cleanup() {
  local exit_code=$?
  echo ""
  echo "--- Cleanup ---"
  echo "Stopping demo background processes..."
  for pid in "${PIDS[@]}"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true

  if [ "$exit_code" -ne 0 ]; then
    echo "❌ Demo failed (exit code $exit_code)."
    echo "Temporary database retained for inspection at: $DEMO_DB"
    echo "Workspace retained at: $DEMO_DIR"
  else
    echo "✅ Demo completed successfully."
    echo "Database: $DEMO_DB"
    rm -rf "$DEMO_DIR"
  fi
}
trap cleanup EXIT INT TERM

get_free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()'
}

SLACK_PORT=$(get_free_port)
LLM_PORT=$(get_free_port)

echo "=================================================="
echo " Starting GPD Deterministic Demo Harness"
echo "=================================================="
echo "Root directory:      $ROOT_DIR"
echo "Demo workspace:      $DEMO_DIR"
echo "Fake Slack port:     $SLACK_PORT"
echo "Fake LLM port:       $LLM_PORT"
echo "Dashboard port:      4041 (running)"
echo "=================================================="

# 1. Start External Service Fakes
echo "[1/7] Starting deterministic external service fakes..."
cd "$ROOT_DIR"
uv run python "$ROOT_DIR/tests/e2e/fake_slack_server.py" --port "$SLACK_PORT" &
PIDS+=($!)

uv run python "$ROOT_DIR/tests/e2e/fake_llm_server.py" --port "$LLM_PORT" &
PIDS+=($!)

sleep 1

# 2. Run Complete Project Memory Loop Demo
echo "[2/7] Initializing GPD, ingesting docs, and processing Slack bug thread..."
uv run python -c "
import os
import sys
from pathlib import Path

repo_root = Path('$ROOT_DIR')
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tests.e2e.test_demo_flow import DemoHarness

workspace = Path('$DEMO_DIR')
harness = DemoHarness(workspace)

# Step 1: Init
print('[Demo] Initializing GPD project...')
project = harness.gpd_init()
print(f'  Project created: {project.get(\"name\")} ({harness.project_id})')

# Step 2: Ingest 3 docs
print('[Demo] Ingesting specification documents...')
harness.add('docs/checkout-prd.md')
harness.add('docs/checkout-frd.md')
harness.add('docs/payment-adr.md')
print('  Ingested checkout-prd.md, checkout-frd.md, payment-adr.md')

# Step 3: Signed Slack bug event
print('[Demo] Submitting signed Slack checkout bug thread...')
task = harness.post_signed_slack_fixture('checkout_bug_thread.json')
print(f'  Created Task: {task[\"public_id\"]} - {task[\"title\"]}')
assert task['public_id'] == 'BUG-1'
assert task['acceptance_criteria'] is None
assert task['summary']
assert task['participants']

# Step 4: Task set & Start session
print('[Demo] Setting task BUG-1 and starting developer session...')
harness.cli('task set BUG-1')
session = harness.cli('start').json()
print(f'  Started Session: {session[\"id\"]} on branch feat/checkout-expired-card')

# Step 5: Context retrieval and parity
print('[Demo] Retrieving budgeted canonical context (CLI & MCP)...')
cli_context = harness.cli('context --format json').json()
mcp_context = harness.mcp('gpd_context_get', {'sessionId': session['id']})
assert cli_context['data']['entry_ids'] == mcp_context['entry_ids']
print(f'  CLI and MCP context parity verified: {len(mcp_context[\"entry_ids\"])} entries')

# Step 6: Overlap detection
print('[Demo] Testing active work overlap detection...')
overlap = harness.start_overlapping_session('src/payment/payment-service.ts')
assert 'work_overlap' in overlap['warnings']
print('  Work overlap conflict detected on src/payment/payment-service.ts')

# Step 7: Finish with fixture diff & knowledge review
print('[Demo] Finishing session with diff and generating knowledge proposal...')
proposal = harness.finish_with_fixture_diff(session['id'])
print(f'  Generated Proposal: {proposal[\"title\"]}')

print('[Demo] Confirming knowledge proposal via CLI human gate...')
confirmed = harness.confirm_proposal_via_cli(proposal['id'])
print(f'  Confirmed Proposal: {confirmed[\"id\"]} -> status: {confirmed[\"status\"]}')

# Step 8: Memory reuse in later task
print('[Demo] Verifying knowledge reuse in subsequent payment task...')
later = harness.context_for_later_payment_task()
assert confirmed['id'] in later['knowledge_ids']
print('  Confirmed decision reused in later payment task context!')

harness.close()
"

echo ""
echo "=================================================="
echo " GPD Demo Completed Successfully!"
echo "=================================================="
echo "Interactive Dashboard URLs:"
echo "  - Task BUG-1:        http://127.0.0.1:4041/tasks/BUG-1"
echo "  - Knowledge Base:    http://127.0.0.1:4041/knowledge"
echo "  - Knowledge Review:  http://127.0.0.1:4041/knowledge/review"
echo "=================================================="
