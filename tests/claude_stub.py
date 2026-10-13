"""A stand-in ``claude`` binary that speaks the Agent SDK's stream-json.

The ``claude-code`` provider drives the real SDK, which starts a real
subprocess and talks the CLI's control protocol over its stdin and stdout.
This stub answers that protocol with a scripted result, so the SDK's own
transport runs end to end with no login and no API cost. What it is to do is
read from a JSON file beside it, which a test rewrites between calls.

Each call appends what it was handed (argv, working directory, the prompt) to
``calls.jsonl`` beside it.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

VERSION = "2.1.300"

_SCRIPT = """\
import json, os, sys, time
from pathlib import Path

here = Path(__file__).parent
if sys.argv[1:2] in (["-v"], ["--version"]):
    print("{version} (Claude Code)")
    sys.exit(0)
plan = json.loads((here / "claude.json").read_text())
time.sleep(plan["sleep"])
for line in sys.stdin:
    message = json.loads(line)
    if message.get("type") == "control_request":
        reply = {{
            "subtype": "success",
            "request_id": message["request_id"],
            "response": {{}},
        }}
        print(json.dumps({{"type": "control_response", "response": reply}}),
              flush=True)
    elif message.get("type") == "user":
        call = {{
            "argv": sys.argv[1:],
            "cwd": os.getcwd(),
            "prompt": message["message"]["content"],
        }}
        with open(here / "calls.jsonl", "a") as calls:
            calls.write(json.dumps(call) + "\\n")
        if plan["result"] is not None:
            print(json.dumps(plan["result"]), flush=True)
        sys.stderr.write(plan["stderr"])
        sys.stderr.flush()
        sys.exit(plan["exit"])
"""


def result(text: str = "a summary", **over: object) -> dict[str, object]:
    """A ``result`` frame as the CLI emits one, successful unless overridden."""
    frame: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 1,
        "duration_api_ms": 1,
        "num_turns": 1,
        "session_id": "stub",
        "result": text,
        "usage": {"input_tokens": 9, "output_tokens": 100},
        "api_error_status": None,
    }
    frame.update(over)
    return frame


def stub_claude(
    directory: Path,
    *,
    answer: dict[str, object] | None = None,
    exit: int = 0,
    stderr: str = "",
    sleep: float = 0.0,
) -> Path:
    """Write (or re-plan) the stub ``claude`` in ``directory``; return it.

    ``answer`` is the result frame to emit, or None for a CLI that dies
    without one.
    """
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "claude"
    binary.write_text(f"#!{sys.executable}\n" + _SCRIPT.format(version=VERSION))
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    plan = {"result": answer, "exit": exit, "stderr": stderr, "sleep": sleep}
    (directory / "claude.json").write_text(json.dumps(plan))
    return binary


def calls(directory: Path) -> list[dict[str, object]]:
    """Every call the stub in ``directory`` has answered, oldest first."""
    log = directory / "calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]
