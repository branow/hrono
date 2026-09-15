"""Is this reply a brief at all? A deterministic shape check on LLM output.

The faithfulness gate (#063) asks whether a brief's claims are supported; this
asks the cruder question it cannot: whether the model summarised the content or
answered the CALLER. In the QA run one node's stored brief was "This appears to
be a condensation format guide with SVG examples, not a request for me to act
on something. Are you shar[ing]..." — the map's first topic was the model
talking back, and the faithfulness gate passed it because it invents nothing
(#103, F21).

Deliberately conservative, because a false positive costs a paid retry and then
pollutes the triage queue the flag exists to serve. Only three shapes are
rejected, each a thing a summary of code or docs does not do:

- ``empty`` — nothing, or too short to be a summary of anything.
- ``asks-the-caller`` — a question containing "you"/"your". A summary describes
  material; it does not interrogate the person who asked for it.
- ``addresses-the-caller`` — an assistant meta-opener in the FIRST sentence
  ("I cannot", "as an AI", "I'd be happy to", "let me know if"). Restricted to
  the opening so a brief that merely quotes such a phrase mid-text is safe.

Everything else passes, including shapes that are merely untidy: a brief with a
generic "## Summary" heading, no heading at all, bullet lists, or an unusual
length. Those are the renderer's problem (#103 chose to fix the export title
there), not evidence the model failed to answer.
"""

from __future__ import annotations

import re

from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
    Usage,
)

MIN_CHARS = 40

_SENTENCE = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")
_ADDRESSES = re.compile(
    r"\bi (?:cannot|can't|am unable|can not|don't have|do not have)\b"
    r"|\bas an ai\b"
    r"|\bi'?d be happy to\b"
    r"|\bi'?m (?:not sure|unable|sorry)\b"
    r"|\blet me know if\b"
    r"|\bcould you (?:clarify|confirm|provide)\b",
    re.IGNORECASE,
)
_YOU = re.compile(r"\byou\b|\byour\b", re.IGNORECASE)


def unusable(text: str) -> str:
    """Return why ``text`` is not a brief, or "" when it is usable."""
    stripped = text.strip()
    if len(stripped) < MIN_CHARS:
        return "empty"
    sentences = [s.strip() for s in _SENTENCE.findall(stripped) if s.strip()]
    if any(s.endswith("?") and _YOU.search(s) for s in sentences):
        return "asks-the-caller"
    if sentences and _ADDRESSES.search(sentences[0]):
        return "addresses-the-caller"
    return ""


def answer(
    completion: Completion, request: CompletionRequest
) -> tuple[CompletionResult, str]:
    """Complete ``request``, retrying ONCE if the reply is not a brief.

    Returns the reply to store and the flag to store beside it: "" when a reply
    passed, otherwise the second reply's reason. Exactly one retry, so a model
    that always answers conversationally terminates after two calls and the
    node keeps a brief — a flagged brief an operator can see and regenerate is
    better than a topic missing from the map (#103, PO 2026-09-14). Usage from
    both calls is summed, because that is what the node cost.
    """
    first = completion.complete(request)
    flag = unusable(first.text)
    if not flag:
        return first, ""
    second = completion.complete(request)
    flag = unusable(second.text)
    return (
        CompletionResult(
            second.text,
            Usage(
                first.usage.input_tokens + second.usage.input_tokens,
                first.usage.output_tokens + second.usage.output_tokens,
            ),
        ),
        flag,
    )
