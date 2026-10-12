"""The agent loop for an API provider: ask, run the tools it calls, repeat.

The provider's own shape is a ``Chat``: how a question, an answer and a tool
result are written into the history, and one request. The loop is the same
for all of them.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from hrono.demo.steps import Steps
from hrono.demo.tools import TOOLS, Library
from hrono.llm.client import LLMError, Usage
from hrono.llm.ledger import Call

# Tool calls one question may make before the loop stops it. A map is a few
# hops deep and a leaf lists a few files, so an agent that needs more is lost.
MOST_CALLS = 16

Message = dict[str, object]


@dataclass(frozen=True)
class Use:
    """One tool call the model asked for."""

    id: str
    tool: str
    args: dict[str, object]


@dataclass(frozen=True)
class Reply:
    """What one request returned: its text, its tool calls, what it cost."""

    text: str
    uses: tuple[Use, ...]
    usage: Usage
    said: Message  # the reply as the history keeps it


class Chat(Protocol):
    """One provider's message shapes and request."""

    def user(self, text: str) -> Message: ...

    def results(self, done: list[tuple[Use, str]]) -> list[Message]: ...

    def ask(self, history: list[Message]) -> Reply: ...


@dataclass
class Looped:
    """A conversation over a ``Chat``; the history outlives each turn."""

    chat: Chat
    library: Library
    steps: Steps
    record: Callable[[Call], None]
    model: str
    provider: str
    history: list[Message] = field(default_factory=list)

    def turn(self, prompt: str) -> None:
        self.history.append(self.chat.user(prompt))
        for _ in range(MOST_CALLS):
            reply = self._ask()
            self.history.append(reply.said)
            if not reply.uses:
                self.steps.add("answer", text=reply.text)
                return
            if reply.text.strip():
                self.steps.add("say", text=reply.text)
            done = [
                (use, self.library.call(use.tool, use.args))
                for use in reply.uses
            ]
            self.history.extend(self.chat.results(done))
        self.steps.add("answer", text=f"Stopped after {MOST_CALLS} tool calls.")

    def _ask(self) -> Reply:
        started = time.monotonic()
        try:
            reply = self.chat.ask(self.history)
        except LLMError:
            self.record(self._call(None, started))
            raise
        self.record(self._call(reply.usage, started))
        return reply

    def _call(self, usage: Usage | None, started: float) -> Call:
        return Call(
            model=self.model,
            role="demo",
            provider=self.provider,
            upstream_model=None if usage is None else usage.model,
            input_tokens=None if usage is None else usage.input_tokens,
            output_tokens=None if usage is None else usage.output_tokens,
            cache_read_tokens=None if usage is None else usage.cache_read,
            cache_creation_tokens=None
            if usage is None
            else usage.cache_creation,
            duration_ms=int((time.monotonic() - started) * 1000),
            ok=usage is not None,
        )


def specs() -> list[dict[str, object]]:
    """The tools as name, description and JSON schema."""
    return [
        {"name": t.name, "description": t.description, "schema": t.schema()}
        for t in TOOLS
    ]
