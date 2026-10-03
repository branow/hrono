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

- ``talks-to-the-caller`` (#217) — a sentence about the CONVERSATION rather
  than the material ("your message is just system context", "there's no
  actual input content", "your prompt got blocked"), or one where the model
  speaks as itself to the reader — a first-person ``I``/``me`` and a ``you`` in
  the same sentence ("I haven't acted on them; say the word if you want...").
  A summary of code or docs describes the material in the third person; the
  two together are an assistant offering, refusing or explaining itself. Both
  shapes reached the export's root page on the 2026-10-03 review tree, and
  neither asked a question, so the rules above passed them.

Everything else passes, including shapes that are merely untidy: a brief with a
generic "## Summary" heading, no heading at all, bullet lists, or an unusual
length. Those are the renderer's problem (#103 chose to fix the export title
there), not evidence the model failed to answer.
"""

from __future__ import annotations

import re
from collections.abc import Callable

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
_CONVERSATION = re.compile(
    r"\byour (?:message|prompt|request|input)\b"
    r"|\bthere(?:'s|\u2019s| is) no (?:actual |real )?"
    r"(?:task|question|input|content|user message)\b"
    r"|\bno actual (?:task|question|input|content)\b",
    re.IGNORECASE,
)
# "I" as a pronoun, not the I of "I/O"; case-sensitive on purpose.
_ME = re.compile(r"(?<![\w/])(?:I(?:['\u2019](?:ll|ve|m|d))?|me)(?![\w/])")
_QUOTED = re.compile(
    r"(?<!\w)'[^']*'(?!\w)|\"[^\"]*\"|\u201c[^\u201d]*\u201d"
    r"|\u2018[^\u2019]*\u2019(?!\w)|`[^`]*`"
)
_LEADING = re.compile(r"^[^A-Za-z]*")
_TAIL = re.compile(r"^(?:$|[-*+]\s|references:|sources:|\w+://)", re.IGNORECASE)


def unusable(text: str) -> str:
    """Return why ``text`` is not a brief, or "" when it is usable.

    The conversational checks run BEFORE the length floor (E015): "Could you
    paste the file for me?" is under ``MIN_CHARS``, and reading it as merely
    short hid it from ``talks_back``, which forgives short.
    """
    stripped = text.strip()
    if not stripped:
        return "empty"
    reason = _answers_the_caller(stripped)
    if reason:
        return reason
    return "empty" if len(stripped) < MIN_CHARS else ""


def talks_back(text: str) -> str:
    """``unusable`` without the length floor, for a CONDENSATION (#221).

    A brief summarises a topic and is never legitimately a few words; a
    condensation summarises one section, and a two-line ``__init__.py`` has a
    true condensation shorter than ``MIN_CHARS``. Only the model answering the
    caller disqualifies one. Nothing at all still does.
    """
    stripped = text.strip()
    return _answers_the_caller(stripped) if stripped else "empty"


def _answers_the_caller(text: str) -> str:
    """Which conversational shape ``text`` has, or "" for none."""
    sentences = _prose(text)
    if sentences and _interrogates(sentences[-1]):
        return "asks-the-caller"
    if sentences and _ADDRESSES.match(_LEADING.sub("", sentences[0])):
        return "addresses-the-caller"
    if any(_converses(sentence) for sentence in sentences):
        return "talks-to-the-caller"
    return ""


def _converses(sentence: str) -> bool:
    """Is this sentence about the exchange, or the model speaking to a you?"""
    if _CONVERSATION.search(sentence):
        return True
    spoken = _QUOTED.sub("", sentence)  # a quote is the material talking
    return bool(_ME.search(spoken) and _YOU.search(spoken))


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
    completion: Completion,
    request: CompletionRequest,
    gate: Callable[[str], str] = unusable,
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
    flag = gate(first.text)
    if not flag:
        return first, ""
    second = completion.complete(request)
    flag = gate(second.text)
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
