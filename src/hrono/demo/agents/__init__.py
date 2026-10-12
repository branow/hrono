"""The agent loop, one kind per way a connection reaches a model.

``claude-code`` runs the Claude Code CLI itself, which runs its own loop and
calls the tools over MCP (``mcp``). The API providers share one loop
(``loop``) and differ only in how a message is written (``anthropic``,
``openai``).
"""

from __future__ import annotations

from typing import Protocol


class Agent(Protocol):
    """A conversation with one model, a question at a time."""

    def turn(self, prompt: str) -> None:
        """Answer ``prompt``, adding its steps; ``LLMError`` on failure."""
        ...
