"""QA-only Anthropic-Messages-compatible proxy backed by `claude -p`.

hrono's LLM client speaks the anthropic SDK and honours a connection
`endpoint`, so pointing a connection at this server makes every condense /
brief / judge call run through the local Claude Code CLI as a subprocess. No
API key, no production code change.

Endpoints: GET /v1/models (connection validation), POST /v1/messages.
Every call is appended to logs/llm-calls.jsonl and dumped in full under
artifacts/llm/ so the run is auditable after the fact.

Usage: python claude_code_proxy.py --port 8788 --model haiku
"""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALL_LOG = ROOT / "logs" / "llm-calls.jsonl"
DUMP_DIR = ROOT / "artifacts" / "llm"
# The CLI must run OUTSIDE this repo: from any cwd inside it, Claude Code loads
# the project CLAUDE.md into the system prompt and answers as the hrono dev
# agent instead of summarising the content it was handed.
CLI_CWD = Path("/private/tmp/claude-501/-Users-orest-repos-hrono/"
               "314b71f8-9fdf-481f-b0eb-8f43b6bb4926/scratchpad/llmcwd")
LOCK = threading.Lock()
COUNTER = {"n": 0}


def run_claude(model: str, system: str, content: str, timeout: float) -> str:
    argv = [
        "claude",
        "-p",
        "--model",
        model,
        "--max-turns",
        "1",
        "--exclude-dynamic-system-prompt-sections",
    ]
    if system:
        argv += ["--system-prompt", system]
    argv += ["--allowed-tools", ""]
    completed = subprocess.run(
        argv,
        input=content,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(CLI_CWD),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"claude exited {completed.returncode}: "
            f"stderr={completed.stderr.strip()[:400]} "
            f"stdout={completed.stdout.strip()[:400]}"
        )
    return completed.stdout.strip()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    model_alias = "haiku"
    call_timeout = 300.0

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/").endswith("/v1/models"):
            self._send(
                200,
                {
                    "data": [
                        {
                            "id": self.model_alias,
                            "type": "model",
                            "display_name": "claude-code-proxy",
                        }
                    ],
                    "has_more": False,
                },
            )
            return
        self._send(404, {"error": {"type": "not_found", "message": self.path}})

    def do_POST(self) -> None:
        if not self.path.rstrip("/").endswith("/v1/messages"):
            self._send(
                404, {"error": {"type": "not_found", "message": self.path}}
            )
            return
        length = int(self.headers.get("content-length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        system = request.get("system") or ""
        if isinstance(system, list):
            system = "\n".join(
                block.get("text", "") for block in system if isinstance(block, dict)
            )
        messages = request.get("messages") or []
        content = ""
        for message in messages:
            value = message.get("content")
            if isinstance(value, str):
                content += value
            elif isinstance(value, list):
                content += "".join(
                    block.get("text", "")
                    for block in value
                    if isinstance(block, dict)
                )
        model = self.model_alias
        with LOCK:
            COUNTER["n"] += 1
            index = COUNTER["n"]
        started = time.time()
        error = None
        try:
            text = run_claude(model, system, content, self.call_timeout)
        except Exception as exc:  # noqa: BLE001 - QA harness reports anything
            error = f"{type(exc).__name__}: {exc}"
            text = ""
        elapsed = round(time.time() - started, 2)
        self._record(index, model, system, content, text, elapsed, error)
        if error is not None:
            self._send(
                500, {"error": {"type": "api_error", "message": error}}
            )
            return
        self._send(
            200,
            {
                "id": f"msg_{uuid.uuid4().hex[:16]}",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": max(1, len(content) // 4),
                    "output_tokens": max(1, len(text) // 4),
                },
            },
        )

    def _record(
        self,
        index: int,
        model: str,
        system: str,
        content: str,
        text: str,
        elapsed: float,
        error: str | None,
    ) -> None:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
        name = f"call-{index:04d}.json"
        (DUMP_DIR / name).write_text(
            json.dumps(
                {
                    "index": index,
                    "model": model,
                    "system": system,
                    "content": content,
                    "response": text,
                    "seconds": elapsed,
                    "error": error,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with LOCK, CALL_LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "index": index,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "model": model,
                        "system_chars": len(system),
                        "content_chars": len(content),
                        "response_chars": len(text),
                        "seconds": elapsed,
                        "error": error,
                        "dump": f"artifacts/llm/{name}",
                    }
                )
                + "\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    Handler.model_alias = args.model
    Handler.call_timeout = args.timeout
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"claude-code proxy on http://127.0.0.1:{args.port} model={args.model}")
    server.serve_forever()


if __name__ == "__main__":
    main()
