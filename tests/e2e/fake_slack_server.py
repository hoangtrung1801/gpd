"""Deterministic Fake Slack Server for GPD E2E testing and demo harness.

Implements:
- conversations.replies: thread retrieval for recorded checkout bug thread
- chat.postMessage: captures and acknowledges posted messages
- HMAC-SHA256 signature helpers for test events
"""

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse


def load_checkout_thread_fixture() -> dict[str, Any]:
    candidates = [
        Path("fixtures/slack/checkout_bug_thread.json"),
        Path(__file__).resolve().parents[2] / "fixtures" / "slack" / "checkout_bug_thread.json",
    ]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {
        "event_id": "Ev_CHECKOUT_001",
        "messages": [
            {
                "ts": "1726137600.000100",
                "user": "U_BOB",
                "text": "Checkout hangs on expired card in staging.",
                "thread_ts": "1726137600.000100",
            }
        ],
    }


def sign_slack_payload(payload: dict[str, Any] | bytes, secret: str) -> tuple[bytes, dict[str, str]]:
    """Compute Slack v0 HMAC-SHA256 signature for payload."""
    if isinstance(payload, dict):
        raw_body = json.dumps(payload).encode("utf-8")
    else:
        raw_body = payload
    timestamp = str(int(time.time()))
    sig_basestring = f"v0:{timestamp}:".encode("utf-8") + raw_body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": sig,
    }
    return raw_body, headers


class FakeSlackHandler(BaseHTTPRequestHandler):
    server: "FakeSlackHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Quiet logs during tests

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/health", "/"):
            self._send_json(200, {"ok": True, "status": "ok", "service": "fake_slack"})
            return

        if path in ("/api/conversations.replies", "/conversations.replies"):
            fixture = load_checkout_thread_fixture()
            msgs = fixture.get("messages", [])
            self._send_json(200, {"ok": True, "messages": msgs, "has_more": False})
            return

        if path == "/api/test/messages":
            self._send_json(200, {"ok": True, "posted_messages": self.server.posted_messages})
            return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        payload: dict[str, Any] = {}
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                payload = {}
        else:
            try:
                parsed_qs = parse_qs(post_data.decode("utf-8"))
                payload = {k: v[0] if len(v) == 1 else v for k, v in parsed_qs.items()}
            except Exception:
                payload = {}

        if path in ("/api/conversations.replies", "/conversations.replies"):
            fixture = load_checkout_thread_fixture()
            msgs = fixture.get("messages", [])
            self._send_json(200, {"ok": True, "messages": msgs, "has_more": False})
            return

        if path in ("/api/chat.postMessage", "/chat.postMessage"):
            channel = payload.get("channel", "C_DEFAULT")
            text = payload.get("text", "")
            thread_ts = payload.get("thread_ts", "")
            msg_record = {
                "channel": channel,
                "text": text,
                "thread_ts": thread_ts,
                "ts": f"{time.time():.6f}",
                "user": "U_GPD_BOT",
            }
            self.server.posted_messages.append(msg_record)
            self._send_json(
                200,
                {
                    "ok": True,
                    "channel": channel,
                    "ts": msg_record["ts"],
                    "message": msg_record,
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "not_found"})


class FakeSlackHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, FakeSlackHandler)
        self.posted_messages: list[dict[str, Any]] = []


class FakeSlackServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.requested_port = port
        self.server: FakeSlackHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int = port

    def start(self) -> str:
        self.server = FakeSlackHTTPServer((self.host, self.requested_port))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.get_url()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def posted_messages(self) -> list[dict[str, Any]]:
        return self.server.posted_messages if self.server else []

    def __enter__(self) -> "FakeSlackServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Fake Slack Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9091, help="Port to bind to")
    args = parser.parse_args()

    server = FakeSlackHTTPServer((args.host, args.port))
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}"
    print(f"Fake Slack server running on {url}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
