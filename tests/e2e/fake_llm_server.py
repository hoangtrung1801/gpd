"""Deterministic Fake LLM Server for GPD E2E testing and demo harness.

Features:
- Schema-valid recordings keyed by (workflow, prompt_version)
- Preloaded fixtures for bug-extraction-checkout and knowledge-extraction-payment
- OpenAI-compatible /v1/chat/completions and /v1/embeddings
- Configurable transient failures and invalid-schema simulation modes
- Runs credential-free on local loopback
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse


def _load_json_fixture(rel_path: str) -> dict[str, Any]:
    candidates = [
        Path(rel_path),
        Path(__file__).resolve().parents[2] / rel_path,
    ]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


class FakeLlmHandler(BaseHTTPRequestHandler):
    server: "FakeLlmHTTPServer"

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
            self._send_json(200, {
                "ok": True,
                "status": "ok",
                "service": "fake_llm",
                "recordings": list(self.server.recordings.keys()),
            })
            return

        if path == "/config":
            self._send_json(200, {
                "transient_failures_remaining": self.server.transient_failures_remaining,
                "invalid_schema_mode": self.server.invalid_schema_mode,
            })
            return

        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        payload: dict[str, Any] = {}
        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            pass

        # Handle simulation configuration
        if path == "/config":
            if "transient_failures" in payload:
                self.server.transient_failures_remaining = int(payload["transient_failures"])
            if "invalid_schema" in payload:
                self.server.invalid_schema_mode = bool(payload["invalid_schema"])
            self._send_json(200, {"ok": True})
            return

        # Check for simulated transient error
        if self.server.transient_failures_remaining > 0 or self.headers.get("X-Simulate-Transient") == "true":
            if self.server.transient_failures_remaining > 0:
                self.server.transient_failures_remaining -= 1
            self._send_json(503, {
                "error": {
                    "message": "Simulated rate limit / transient gateway unavailable",
                    "type": "rate_limit_error",
                    "code": 503,
                }
            })
            return

        # Check for simulated invalid schema
        if self.server.invalid_schema_mode or self.headers.get("X-Simulate-Invalid-Schema") == "true":
            self._send_json(200, {
                "error": "invalid_schema",
                "title": None,
                "invalid_field": 12345,
                "confidence": "not-a-float",
            })
            return

        # Direct structured completion endpoint
        if path in ("/api/v1/llm/structured", "/generate_structured", "/generate"):
            workflow = payload.get("workflow", "bug_extraction")
            version = str(payload.get("schema_version") or payload.get("version") or "1.0")
            key = (workflow, version)
            data = self.server.recordings.get(key)
            if not data:
                # Fallback to any recording with matching workflow
                for (wf, v), rec in self.server.recordings.items():
                    if wf == workflow:
                        data = rec
                        break
            if not data:
                data = self.server.recordings.get(("bug_extraction", "1.0"), {})

            self._send_json(200, {
                "data": data,
                "workflow": workflow,
                "schema_version": version,
                "input_tokens": 120,
                "output_tokens": 65,
                "model": "fake-llm-1",
            })
            return

        # OpenAI chat completions
        if path in ("/v1/chat/completions", "/chat/completions"):
            messages = payload.get("messages", [])
            full_prompt = " ".join(m.get("content", "") for m in messages if isinstance(m, dict)).lower()

            # Key determination
            if "knowledge" in full_prompt or "normalize" in full_prompt or "adr" in full_prompt:
                recording = self.server.recordings.get(("knowledge_extraction", "1.0"))
            else:
                recording = self.server.recordings.get(("bug_extraction", "1.0"))

            content_str = json.dumps(recording or {})

            response = {
                "id": "chatcmpl-fake-deterministic",
                "object": "chat.completion",
                "created": 1726137600,
                "model": payload.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content_str,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 65,
                    "total_tokens": 185,
                },
            }
            self._send_json(200, response)
            return

        # OpenAI embeddings
        if path in ("/v1/embeddings", "/embeddings"):
            inputs = payload.get("input", [])
            if isinstance(inputs, str):
                inputs = [inputs]
            data = []
            for i, _ in enumerate(inputs):
                # Deterministic 384-dimension vector
                vec = [0.05 * ((j % 10) - 5) for j in range(384)]
                data.append({"object": "embedding", "embedding": vec, "index": i})
            self._send_json(200, {
                "object": "list",
                "data": data,
                "model": payload.get("model", "text-embedding-3-small"),
                "usage": {"prompt_tokens": 10 * len(inputs), "total_tokens": 10 * len(inputs)},
            })
            return

        self._send_json(404, {"error": "not_found"})


class FakeLlmHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, FakeLlmHandler)
        self.transient_failures_remaining = 0
        self.invalid_schema_mode = False
        self.recordings: dict[tuple[str, str], dict[str, Any]] = {}
        self._load_default_recordings()

    def _load_default_recordings(self) -> None:
        bug_data = _load_json_fixture("fixtures/llm/bug-extraction-checkout.json")
        if bug_data:
            self.recordings[("bug_extraction", "1.0")] = bug_data

        know_data = _load_json_fixture("fixtures/llm/knowledge-extraction-payment.json")
        if know_data:
            self.recordings[("knowledge_extraction", "1.0")] = know_data


class FakeLlmServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.requested_port = port
        self.server: FakeLlmHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int = port

    def start(self) -> str:
        self.server = FakeLlmHTTPServer((self.host, self.requested_port))
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

    def set_transient_failures(self, count: int) -> None:
        if self.server:
            self.server.transient_failures_remaining = count

    def set_invalid_schema(self, enabled: bool) -> None:
        if self.server:
            self.server.invalid_schema_mode = enabled

    def __enter__(self) -> "FakeLlmServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Fake LLM Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9092, help="Port to bind to")
    args = parser.parse_args()

    server = FakeLlmHTTPServer((args.host, args.port))
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}"
    print(f"Fake LLM server running on {url}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
