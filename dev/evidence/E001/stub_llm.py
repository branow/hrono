"""A local openai-compatible endpoint for the E001 e2e (T2a).

No API key is in the dev's environment, so the e2e points an
``openai-compatible`` connection here. Three routes, the same wire shape hrono's
``llm/openai.py`` speaks:

- ``GET /v1/models``: the probe a connection write makes.
- ``POST /v1/embeddings``: a deterministic bag-of-words vector (hashed tokens
  into 64 dims, L2-normalised), so files about the same thing cluster together.
- ``POST /v1/chat/completions``: a plain declarative paragraph that names the
  call number. Every reply is unique, so a stored text that is byte-identical
  after the sync was NOT regenerated, and one that differs WAS.

Every completion request is appended to the log file given as argv[2], so the
transcript shows exactly which calls the sync made.

Usage: python stub_llm.py <port> <call-log.jsonl>
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIMS = 64
_lock = threading.Lock()
_calls = 0


def _vector(text: str) -> list[float]:
    vec = [0.0] * DIMS
    for token in re.findall(r"[a-z]{3,}", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vec[digest[0] % DIMS] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _reply(content: str, number: int) -> str:
    words = re.findall(r"[A-Za-z]{4,}", content)
    topic = " ".join(words[-6:]) or "material"
    digest = hashlib.sha256(content.encode()).hexdigest()[:10]
    return (
        f"This material covers {topic}. It describes the behaviour, the "
        f"inputs and the outputs of the code involved, digest {digest}, "
        f"written as stub reply number {number}."
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - the connection probe
        if not self.path.endswith("/models"):
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps({"data": [{"id": "stub-1"}, {"id": "bow-64"}]})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data.encode())

    def do_POST(self) -> None:  # noqa: N802 - http.server's naming
        global _calls
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):
            inputs = body["input"]
            texts = [inputs] if isinstance(inputs, str) else list(inputs)
            payload: dict[str, object] = {
                "data": [
                    {"index": i, "embedding": _vector(t)}
                    for i, t in enumerate(texts)
                ],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            }
        elif self.path.endswith("/chat/completions"):
            content = body["messages"][-1]["content"]
            with _lock:
                _calls += 1
                number = _calls
                with open(sys.argv[2], "a", encoding="utf-8") as log:
                    log.write(
                        json.dumps(
                            {
                                "call": number,
                                "system": body["messages"][0]["content"][:80],
                                "content_sha": hashlib.sha256(
                                    content.encode()
                                ).hexdigest()[:12],
                                "content_head": content[:120],
                            }
                        )
                        + "\n"
                    )
            payload = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": _reply(content, number),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 30},
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
