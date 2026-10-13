"""What the demo agent is told, and the recall attached to each question.

The attachment is the plugin's (``plugins/hrono/scripts/hooks/recall.js``):
the same head line, the same titles and the same size limit, so the demo
shows what a real session receives.
"""

from __future__ import annotations

from collections.abc import Sequence

from hrono.recall.engine import Hit

LIMIT = 5  # passages per question, the plugin's default
LONGEST = 12_000  # the most recalled text attached, the plugin's default


def system(tree: str) -> str:
    """The agent's instructions: the plugin's session note, for these tools."""
    return (
        "You answer questions about a project. The project has an hrono map "
        f'(tree "{tree}"): briefs of everything its sources hold, from one '
        "overview down to the files. Read it with your tools: "
        'open_topic("root.md") first, then the child whose summary fits the '
        "question, down to a leaf; there, open_source the files listed under "
        "## Sources when you need the code itself. Passages may be attached "
        "to a question as hrono recall: they are a lead on where to look, not "
        "the answer. Before answering, walk the map to the topic the question "
        "belongs to and open the source files it rests on, even when the "
        "recall looks sufficient; never say the information is missing "
        "without having walked the map. Answer briefly and name the files "
        "your answer rests on."
    )


def attachment(tree: str, hits: Sequence[Hit]) -> str | None:
    """The recalled passages as one block, or None when none fit."""
    head = (
        f'hrono recall from tree "{tree}": the passages most likely to '
        "answer this prompt, from its sources and from the map's briefs."
    )
    text = head
    for hit in hits:
        block = f"\n\n### {title(hit)}\n\n{hit.body}"
        if len(text) + len(block) > LONGEST:
            break
        text += block
    return None if text == head else text


def title(hit: Hit) -> str:
    """A passage is named by what a reader can open: its file or its topic."""
    if hit.kind == "summary":
        return f"brief of topic {hit.topic}"
    if hit.path:
        return f"{hit.path} ({hit.source})" if hit.source else hit.path
    return hit.header or "passage"


def prompt(question: str, attached: str | None) -> str:
    """The question as the model receives it, with the hook's attachment."""
    if attached is None:
        return question
    return f"<hrono-recall>\n{attached}\n</hrono-recall>\n\n{question}"
