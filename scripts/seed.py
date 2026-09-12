"""Seed dev DB (.gpd/gpd.db) with demo data. Idempotent; safe to re-run.

Seeds: project + PRD/FRD/ADR sources (via HTTP), BUG-1 from the Slack
fixture (via domain services + fixture LLM recording, no live LLM),
two overlapping developer sessions, one knowledge proposal, one
contradictory-knowledge conflict.

Usage: uv run python scripts/seed.py  (from repo root)
"""

import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
ROOT = Path(os.environ.get("GPD_REPO_ROOT", Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(ROOT / "backend" / "src"))

API = "http://100.67.176.76:4040"
TOKEN = "dev-local-token"


def api(method, path, body=None, key=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
            **({"Idempotency-Key": key} if key else {}),
        },
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())


def get_list(path):
    _, res = api("GET", path)
    return res.get("data") or []


# 1. Project (reuse if present)
projects = get_list("/api/v1/projects")
proj = next((p for p in projects if p["name"] == "Checkout"), None)
if proj is None:
    s, created = api(
        "POST", "/api/v1/projects",
        {"name": "Checkout", "team_identifier": "payments",
         "repository_root": "/home/work/gpd", "default_branch": "main"},
        key="seed-demo",
    )
    proj = created["data"]
    print("project created:", proj["id"], s)
else:
    print("project reused:", proj["id"])
pid = proj["id"]

# 2. Sources
source_ids = {}
for fname, stype, title, key in [
    ("checkout-prd.md", "prd", "Checkout PRD", "seed-prd"),
    ("checkout-frd.md", "frd", "Checkout FRD", "seed-frd"),
    ("payment-adr.md", "adr", "Payment ADR", "seed-adr"),
]:
    content = (ROOT / "fixtures" / "demo-project" / "docs" / fname).read_text()
    s, res = api(
        "POST", f"/api/v1/projects/{pid}/sources",
        {"type": stype, "title": title, "content": content,
         "canonical_ref": f"docs/{fname}", "author": "seed"},
        key=key,
    )
    sid = (res.get("data") or {}).get("source_id")
    source_ids[stype] = sid
    print(f"source {fname}:", s, sid)

# 3. BUG-1 (skip if present)
tasks = get_list("/api/v1/tasks")
bug = next((t for t in tasks if t.get("public_id") == "BUG-1"), None)
if bug is None:
    from gpd.conversations.schemas import ConversationCreate, ConversationMessageCreate
    from gpd.conversations.service import ConversationService
    from gpd.db.engine import Database
    from gpd.llm.recording import FakeLlmGateway
    from gpd.llm.workflows.bug_extraction import BugExtraction, BugExtractionWorkflow
    from gpd.tasks.service import TaskService

    fixture = json.loads((ROOT / "fixtures" / "slack" / "checkout_bug_thread.json").read_text())
    recording = json.loads((ROOT / "fixtures" / "llm" / "bug-extraction-checkout.json").read_text())
    msgs = fixture["messages"]
    ts = [m["ts"] for m in msgs]
    # Validate recording evidence against the real thread message ids
    extraction = BugExtraction.model_validate({
        k: v for k, v in recording.items() if k not in ("workflow", "version")
    })

    async def make_bug():
        db = Database.open(ROOT / ".gpd" / "gpd.db")
        conv_svc = ConversationService(db)
        conv = await conv_svc.save_conversation(ConversationCreate(
            channel_id="C123", thread_ts=ts[0], title="Checkout expired-card thread",
            project_id=pid,
            messages=[ConversationMessageCreate(
                external_message_id=m["ts"], author=m.get("user", "U_UNKNOWN"),
                text=m.get("text", ""), timestamp=m["ts"], ordering=i,
            ) for i, m in enumerate(msgs)],
        ))
        llm = FakeLlmGateway()
        llm.respond(extraction)
        svc = TaskService(db, BugExtractionWorkflow(llm))
        detail = await svc.create_bug_from_conversation(conv, idempotency_key="seed-bug-1")
        db.close()
        return detail

    bug = asyncio.run(make_bug())
    print("BUG created:", bug.public_id, "-", bug.title)
    bug_id, bug_public = bug.id, bug.public_id
else:
    print("BUG-1 reused:", bug["id"])
    bug_id, bug_public = bug["id"], bug["public_id"]

# 4. Sessions (alice + overlapping bob)
from gpd.db.engine import Database
from gpd.sessions.schemas import ChangedFile, StartSessionRequest
from gpd.sessions.service import SessionService

sessions = get_list("/api/v1/sessions")
have_alice = any(s.get("developer") == "alice" and s.get("status") == "active" for s in sessions)


async def make_sessions():
    db = Database.open(ROOT / ".gpd" / "gpd.db")
    svc = SessionService(db)
    out = []
    if not have_alice:
        file = ChangedFile(path="src/payment/payment-service.ts", change_kind="modified")
        s1, w1, _ = await svc.start(StartSessionRequest(
            project_id=pid, task_id=bug_id, developer="alice",
            agent="claude-code", repo_path="/home/work/gpd", changed_files=[file],
        ), "seed-session-alice")
        print("session alice:", s1.id, "warnings:", [w.severity for w in w1])
        s2, w2, _ = await svc.start(StartSessionRequest(
            project_id=pid, task_id=None, developer="bob",
            agent="codex", repo_path="/home/work/gpd", changed_files=[file],
        ), "seed-session-bob")
        print("session bob:", s2.id, "warnings:", [(w.severity, w.explanation[:60]) for w in w2])
        out = [s1.id, s2.id]
    else:
        print("sessions reused")
    db.close()
    return out


session_ids = asyncio.run(make_sessions())

# 5. Knowledge proposal (from fixture recording)
proposals = get_list("/api/v1/knowledge/proposals")
if not any(p.get("title") == "Normalize payment errors in PaymentService" for p in proposals):
    from gpd.knowledge.proposals import ProposalRepository

    recording = json.loads((ROOT / "fixtures" / "llm" / "knowledge-extraction-payment.json").read_text())
    first = recording["proposals"][0]

    async def make_proposal():
        db = Database.open(ROOT / ".gpd" / "gpd.db")

        def _write():
            with db.session() as session:
                with session.begin():
                    return ProposalRepository().create(
                        session, project_id=pid, type=first["type"],
                        title=first["title"], content=first["content"],
                        confidence=first["confidence"],
                        session_id=session_ids[0] if session_ids else None,
                        evidence=first.get("evidence", []),
                        workflow_version=recording.get("version", "1.0"),
                    ).id

        prop_id = await db.write(_write)
        db.close()
        return prop_id

    print("proposal created:", asyncio.run(make_proposal()))
else:
    print("proposal reused")

# 6. Contradictory-knowledge conflict (retry policy: PRD vs ADR)
conflicts = get_list("/api/v1/conflicts")
if not any("retry" in (c.get("explanation") or "").lower() for c in conflicts):
    from gpd.conflicts.repository import ConflictRepository
    from gpd.sessions.schemas import ConflictEvidenceSchema

    async def make_conflict():
        db = Database.open(ROOT / ".gpd" / "gpd.db")

        def _write():
            with db.session() as session:
                with session.begin():
                    return ConflictRepository().create(
                        session, project_id=pid, type="contradictory_knowledge",
                        severity="high",
                        explanation=("Retry policy conflict: PRD says retry payment "
                                     "three times; ADR says retries were reduced to one."),
                        detector_version="seed-1.0",
                        evidence=[
                            ConflictEvidenceSchema(
                                kind="source", target_type="source",
                                target_id=source_ids.get("prd", ""),
                                detail="Retry payment three times"),
                            ConflictEvidenceSchema(
                                kind="source", target_type="source",
                                target_id=source_ids.get("adr", ""),
                                detail="Retries were reduced to one"),
                        ],
                    ).id

        cid = await db.write(_write)
        db.close()
        return cid

    print("conflict created:", asyncio.run(make_conflict()))
else:
    print("conflict reused")

print("tasks:", [(t.get("public_id"), t.get("title")) for t in get_list("/api/v1/tasks")])
print("sessions:", [(s.get("developer"), s.get("status")) for s in get_list("/api/v1/sessions")])
print("done")
