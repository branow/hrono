"""The demo agent as the Claude Code CLI, with only the demo's tools.

    claude -p --setting-sources "" --strict-mcp-config --disable-slash-commands
      --mcp-config <hrono at url> --tools "" --allowedTools <the two tools>
      --output-format stream-json --verbose --model <m> --system-prompt <s>
      [--resume <session>]   < prompt on stdin

``--safe-mode``, which the summarizer uses, also drops an ``--mcp-config``
passed on the command line, so the operator's customizations are dropped
one by one instead: no settings files (and so no plugins or hooks), no other
MCP servers, no skills, no built-in tools. The CLI then has the two tools
and nothing else, and runs from hrono's own empty directory, so it reads no
project memory.

The CLI runs the loop itself and calls the tools over MCP (``mcp``), so the
tool steps come from the server's side; this reads the CLI's stream for what
the model says and for the answer.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from hrono.demo.agents.loop import MOST_CALLS
from hrono.demo.agents.mcp import NAME
from hrono.demo.steps import Steps
from hrono.demo.tools import TOOLS
from hrono.llm.client import LLMError
from hrono.llm.ledger import Call

Run = Callable[[list[str], Path, str], Iterable[str]]


@dataclass
class ClaudeCode:
    """A CLI conversation: each turn resumes the session the first began."""

    model: str
    system: str
    url: str  # where this conversation's tools are served
    workdir: Path
    steps: Steps
    record: Callable[[Call], None]
    run: Run | None = None  # the CLI's stdout lines; a test seam
    session: str | None = None

    def turn(self, prompt: str) -> None:
        started = time.monotonic()
        result: dict[str, object] | None = None
        try:
            for line in (self.run or _run)(
                self.command(), self.workdir, prompt
            ):
                result = self._read(line) or result
        finally:
            self.record(self._call(result, started))
        if result is None:
            raise LLMError("claude-code ended without an answer")
        if result.get("is_error") or result.get("subtype") != "success":
            said = result.get("result") or result.get("subtype")
            raise LLMError(f"claude-code stopped: {said}")
        self.steps.add("answer", text=str(result.get("result") or ""))

    def command(self) -> list[str]:
        servers = {NAME: {"type": "http", "url": self.url}}
        command = [
            "claude",
            "-p",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--mcp-config",
            json.dumps({"mcpServers": servers}),
            "--tools",
            "",
            "--allowedTools",
            ",".join(f"mcp__{NAME}__{tool.name}" for tool in TOOLS),
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            self.model,
            "--system-prompt",
            self.system,
            "--max-turns",
            str(MOST_CALLS),
        ]
        if self.session:
            command += ["--resume", self.session]
        return command

    def _read(self, line: str) -> dict[str, object] | None:
        """Take one stream event; the final ``result`` event is returned."""
        try:
            event = json.loads(line)
        except ValueError:
            return None
        if not isinstance(event, dict):
            return None
        if event.get("type") == "system" and event.get("subtype") == "init":
            self.session = str(event.get("session_id") or self.session or "")
        elif event.get("type") == "assistant":
            self._said(event)
        elif event.get("type") == "result":
            return event
        return None

    def _said(self, event: dict[str, object]) -> None:
        """Text beside a tool call is narration; the answer comes as result."""
        message = event.get("message")
        blocks = message.get("content") if isinstance(message, dict) else None
        if not isinstance(blocks, list):
            return
        if not any(
            b.get("type") == "tool_use" for b in blocks if isinstance(b, dict)
        ):
            return
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    self.steps.add("say", text=text)

    def _call(self, result: dict[str, object] | None, started: float) -> Call:
        usage = result.get("usage") if result else None
        usage = usage if isinstance(usage, dict) else None
        return Call(
            model=self.model,
            role="demo",
            provider="claude-code",
            upstream_model=None,
            input_tokens=_count(usage, "input_tokens"),
            output_tokens=_count(usage, "output_tokens"),
            cache_read_tokens=_count(usage, "cache_read_input_tokens"),
            cache_creation_tokens=_count(usage, "cache_creation_input_tokens"),
            duration_ms=int((time.monotonic() - started) * 1000),
            ok=bool(result) and not result.get("is_error"),  # type: ignore[union-attr]
        )


def _count(usage: dict[str, object] | None, key: str) -> int | None:
    value = usage.get(key) if usage else None
    return value if isinstance(value, int) else None


# Long enough for a walk of the map and a few files; a stuck CLI is stopped.
TIMEOUT = 600.0


def _run(command: list[str], workdir: Path, prompt: str) -> Iterable[str]:
    """The CLI's stdout, a line at a time as it writes them."""
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(  # noqa: S603 - a fixed argv, no shell
            command,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise LLMError("claude-code CLI could not be run") from exc
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(prompt)
    process.stdin.close()
    deadline = time.monotonic() + TIMEOUT
    try:
        for line in process.stdout:
            yield line
            if time.monotonic() > deadline:
                raise LLMError("claude-code took too long")
        process.wait(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
