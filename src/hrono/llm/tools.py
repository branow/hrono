"""Read-only tools a completion may call before it answers.

A brief writer that can look up the other side of a connection - who consumes
the message a topic publishes, what an endpoint it calls really selects -
states facts no topic's own material holds (docs/evaluations/
2026-10-defines-uses/, rounds 8 and 9). The tools are hrono's own Python
functions, never a shell: a ``Toolbox`` names them, says what each takes, and
answers each call. Every provider runs the same loop over it - call, answer,
call again - until the model writes its answer or the toolbox's call budget
is spent, after which every further call is answered with ``SPENT`` so the
model writes with what it has.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

SPENT = "No lookups left. Write the answer now with what you found."


@dataclass(frozen=True)
class Tool:
    """One tool as the model sees it: a name, what it does, its arguments."""

    name: str
    description: str
    parameters: Mapping[str, object]  # a JSON schema of type "object"


@dataclass
class Toolbox:
    """The tools of one call, their answers, and what was asked of them.

    ``answer`` is called with a tool's name and arguments and returns the text
    the model reads; it must never raise for a bad argument, but say what was
    wrong, as a tool result the model can act on. ``most`` caps the calls;
    ``calls`` records each one, in order, for the caller to keep.
    """

    tools: tuple[Tool, ...]
    answer: Callable[[str, Mapping[str, object]], str]
    most: int = 15
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def call(self, name: str, arguments: Mapping[str, object]) -> str:
        """Answer one call, or say the budget is spent."""
        if len(self.calls) >= self.most:
            return SPENT
        self.calls.append((name, dict(arguments)))
        if name not in {tool.name for tool in self.tools}:
            return f"No tool named {name}."
        return self.answer(name, arguments)

    @property
    def turns(self) -> int:
        """Model turns the loop may take: one per call, and the answer."""
        return self.most + 2
