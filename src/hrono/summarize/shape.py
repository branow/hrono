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
- ``asks-the-caller`` — a ``you``-bearing question that is the LAST sentence and
  carries no reporting cue. A summary describes material; it does not
  interrogate the person who asked for it. Both qualifiers are what let it tell
  interrogating from QUOTING (#121): a brief that quotes a question out of its
  source carries on afterwards, because the quote is evidence for a point it
  then makes, and one that REPORTS a question says so ("the docstring opens
  with", "the final entry asks:"). A brief that interrogates ends on its
  question and introduces nobody. Without those two the check rejected an FAQ
  summary, a docstring that opens by asking, and any brief reporting a question
  in its material — which is what a Confluence or Notion corpus is largely made
  of.
- ``addresses-the-caller`` — an assistant meta-opener that STARTS the first
  sentence ("I cannot", "as an AI", "I'd be happy to", "let me know if").
  Anchored to the opening so a brief that quotes such a phrase mid-text is safe
  — which the rule always claimed, while actually scanning the whole first
  sentence (#121).

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
_REPORTS = re.compile(
    r"\basks?\b|\basking\b|\bopens? with\b|\bbegins? with\b"
    r"|\bquestions?\s+(?:answered|include|covered)\b|\breads\b"
    r"|\btitled\b|\bentitled\b"
    r"|[\"\u201c\u2018]",  # a QUOTE mark, never an apostrophe: "you'd" is not
    re.IGNORECASE,
)
_LEADING = re.compile(r"^[^A-Za-z]*")
_TAIL = re.compile(r"^(?:$|[-*+]\s|references:|sources:|\w+://)", re.IGNORECASE)


def unusable(text: str) -> str:
    """Return why ``text`` is not a brief, or "" when it is usable."""
    stripped = text.strip()
    if len(stripped) < MIN_CHARS:
        return "empty"
    sentences = _prose(stripped)
    if sentences and _interrogates(sentences[-1]):
        return "asks-the-caller"
    if sentences and _ADDRESSES.match(_LEADING.sub("", sentences[0])):
        return "addresses-the-caller"
    return ""


def _prose(text: str) -> list[str]:
    """The reply's sentences, with any trailing NON-prose tail dropped (#121).

    "The question must be last" is a signal about prose only. A brief that ends
    with a reference list or bullets — which stored briefs did before #102 moved
    the URI footer out of the text — would otherwise hide an interrogating
    question behind its own footer and read as usable.

    The tail is dropped by LINE rather than by sentence, because the sentence
    splitter cuts a URI at every dot and the fragments look like prose.
    """
    lines = text.splitlines()
    while lines and _TAIL.match(lines[-1].strip()):
        lines.pop()
    body = "\n".join(lines)
    return [s.strip() for s in _SENTENCE.findall(body) if s.strip()]


def _interrogates(last: str) -> bool:
    """Is this closing sentence a question AT the caller (#121)?

    Three things have to hold together: it is a question, it is about "you",
    and nothing marks it as reported or quoted. Any one of them alone catches
    ordinary material — an FAQ, a how-to, a docstring that opens by asking.
    """
    if not last.endswith("?") or not _YOU.search(last):
        return False
    return not _REPORTS.search(last)


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
