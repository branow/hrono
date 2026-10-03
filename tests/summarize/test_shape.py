"""#103: the shape guard between the model and the stored tree."""

import json
from pathlib import Path

import pytest

from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.summarize.shape import answer, talks_back, unusable

# the reply that was actually stored as a topic's brief in the QA run (F21)
F21 = (
    "This appears to be a condensation format guide with SVG examples, not a "
    "request for me to act on something. Are you sharing this as a reference "
    "pattern for how you want complex data summarized going forward, or do "
    "you have actual SVG content you'd like me to condense right now?"
)
GOOD = (
    "This is the **ItsDangerous signing library** — it signs and serialises "
    "Python objects, with key rotation and timestamp validation.\n\n"
    "## Caution\n\nThe brief covers the public API only."
)


def test_the_stored_non_answer_is_rejected() -> None:
    assert unusable(F21) == "asks-the-caller"


@pytest.mark.parametrize(
    "reply",
    [
        "I cannot summarise this content without more context about it.",
        "As an AI assistant I do not have access to the files you mention.",
        "I'm not sure what you want here; the material is ambiguous to me.",
        "Could you clarify which of these documents you want summarised?",
    ],
)
def test_assistant_meta_openers_are_rejected(reply: str) -> None:
    assert unusable(reply)


@pytest.mark.parametrize("reply", ["", "   \n  ", "N/A", "No content."])
def test_an_empty_reply_is_rejected(reply: str) -> None:
    assert unusable(reply) == "empty"


@pytest.mark.parametrize(
    "reply",
    [
        GOOD,
        # a generic heading is untidy, not a non-answer: the renderer handles
        # the title (#103), and retrying a good brief costs money for nothing.
        "## Summary\n\nThe module packs sections into passages within budget.",
        # bullets only, no prose intro
        "- signs payloads\n- validates timestamps\n- rotates keys safely now",
        # a question that is ABOUT the material, not addressed to the caller
        "It answers the question: what happens when a signature expires?",
        # the phrase appears mid-text, not as the opener
        "The library signs payloads. Users ask: can I rotate keys? Yes, it "
        "supports a key list for rotation.",
    ],
)
def test_usable_briefs_are_left_alone(reply: str) -> None:
    assert unusable(reply) == ""


@pytest.mark.parametrize(
    ("reply", "why"),
    [
        pytest.param(
            "Could you paste the file for me?", "asks-the-caller", id="asks"
        ),
        pytest.param("I cannot see any file.", "addresses-the-caller", id="me"),
        pytest.param(
            "Your message has no content.", "talks-to-the-caller", id="talks"
        ),
    ],
)
def test_a_short_talk_back_is_caught_under_the_floor(
    reply: str, why: str
) -> None:
    # E015: the length floor ran first and called these "empty", which a
    # condensation forgives, so a short talk-back was never caught
    assert len(reply) < 40
    assert talks_back(reply) == why
    assert unusable(reply) == why


@pytest.mark.parametrize(
    ("reply", "why"),
    [
        pytest.param("Returns 1.", "", id="short-plain"),
        pytest.param("", "empty", id="nothing"),
        pytest.param("  \n ", "empty", id="blank"),
    ],
)
def test_a_short_plain_condensation_is_still_usable(
    reply: str, why: str
) -> None:
    assert talks_back(reply) == why


class FakeCompletion:
    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        reply = self.replies[min(self.calls, len(self.replies)) - 1]
        return CompletionResult(reply, Usage(10, 4))


def _request() -> CompletionRequest:
    return CompletionRequest(model={"name": "m"}, system="", content="x")


def test_a_good_reply_costs_one_call() -> None:
    client = FakeCompletion(GOOD)
    result, flag = answer(client, _request())
    assert client.calls == 1
    assert flag == ""
    assert result.text == GOOD


def test_a_non_answer_is_retried_once_and_the_retry_is_kept() -> None:
    client = FakeCompletion(F21, GOOD)
    result, flag = answer(client, _request())
    assert client.calls == 2
    assert flag == ""
    assert result.text == GOOD
    assert result.usage.input_tokens == 20  # both calls, that is what it cost
    assert result.usage.output_tokens == 8


def test_a_model_that_always_talks_back_terminates_and_flags() -> None:
    client = FakeCompletion(F21, F21, F21)
    result, flag = answer(client, _request())
    assert client.calls == 2  # exactly one retry, never a loop
    assert flag == "asks-the-caller"
    assert result.text == F21  # stored anyway: never drop the node


F21 = (
    "This appears to be a condensation format guide with SVG examples, not a "
    "request for me to act on something. Are you sharing this as a reference "
    "pattern for how you want complex data summarized going forward, or do "
    "you have actual SVG content or documentation you'd like me to condense "
    "right now?"
)

QUOTED_QUESTIONS = [
    # a docstring that opens by asking, then answers itself
    'The module\'s docstring opens with "How do you sign a cookie?" and then '
    "answers it: Signer.sign appends a timestamp and an HMAC.",
    # an FAQ page, which is what a Confluence corpus is largely made of
    "A FAQ covering deployment. Questions answered include: how do I rotate a "
    "key? Can you run this behind a proxy? What happens when a token expires?",
    # a REPORTED question, closing the brief
    "The troubleshooting guide walks through three failure modes. The final "
    "entry asks: why does your token expire early?",
    # a quoted question opening the brief, with the summary continuing
    '"Have you ever needed a signed cookie?" it asks, before introducing '
    "URLSafeTimedSerializer and its max_age parameter.",
]


def test_the_real_f21_brief_is_still_rejected() -> None:
    # the true positive, from the actual stored text in .e2e/run rather than a
    # lookalike: the map's first topic was the model talking back.
    assert unusable(F21) == "asks-the-caller"


@pytest.mark.parametrize("text", QUOTED_QUESTIONS)
def test_a_quoted_or_reported_question_is_usable(text: str) -> None:
    # #121: the rule could not tell interrogating the caller from quoting a
    # question that is IN the material. The exposure is FAQs, troubleshooting
    # pages and second-person how-to docs — exactly the source types on the
    # roadmap.
    assert unusable(text) == ""


def test_an_assistant_phrase_quoted_mid_sentence_is_usable() -> None:
    # the module docstring always promised this; the check actually scanned the
    # whole first sentence, so a quote inside a long opener was rejected.
    text = (
        "The contributing guide tells reviewers to reply 'let me know if you "
        "need more detail' when requesting changes, and documents the "
        "two-approval rule."
    )

    assert unusable(text) == ""


def test_a_genuine_meta_opener_is_still_rejected() -> None:
    text = (
        "I cannot summarise this content because it appears to be a binary "
        "file rather than source code or documentation."
    )

    assert unusable(text) == "addresses-the-caller"


def test_a_footer_cannot_hide_an_interrogating_question() -> None:
    # stored briefs carried a URI footer before #102 moved it out of the text,
    # and the sentence splitter cuts a URI at every dot — so the fragments look
    # like prose and the question stops being "last". Measured: with the tail
    # dropped by LINE, the `.e2e/run` corpus rejects exactly F21 again, which is
    # what the PO recorded before this change.
    with_footer = (
        F21 + "\n\nReferences:\n- git:///repos/chalk/media/logo.svg@661317e\n"
        "- git:///repos/itsdangerous/docs/_static/name.svg@672971d\n"
    )

    assert unusable(with_footer) == "asks-the-caller"


def test_a_brief_that_merely_ends_in_bullets_is_usable() -> None:
    text = (
        "The signer module builds and verifies signatures. It covers:\n"
        "- sign, which appends a timestamp and an HMAC\n"
        "- unsign, which rejects a tampered payload\n"
    )

    assert unusable(text) == ""


def test_a_multi_line_brief_that_ends_by_interrogating_is_rejected() -> None:
    # #121: the tail drop must remove ONLY the non-prose tail. F21's own reply
    # is two sentences on one line; had the model put a blank line before its
    # question — ordinary formatting — a tail drop that ate prose would have
    # thrown the question away and read the brief as usable.
    text = (
        "This appears to be a condensation format guide with SVG examples.\n"
        "\n"
        "Are you sharing this as a reference pattern for what you want?"
    )

    assert unusable(text) == "asks-the-caller"


def test_the_tail_drop_keeps_a_prose_closing_line() -> None:
    # the same guard from the usable side: a brief whose last line is prose
    # keeps that line, so what the check reads is the brief's real ending.
    text = (
        "The signer module builds and verifies signatures.\n"
        "\n"
        "It rejects a tampered payload and honours max_age."
    )

    assert unusable(text) == ""


# Replies stored as briefs on the 2026-10-03 review tree, verbatim (#217), and
# real briefs a model wrote for the prototype corpus, which must still pass.
SEEN = json.loads((Path(__file__).parent / "briefs_seen.json").read_text())


@pytest.mark.parametrize(
    "text",
    [pytest.param(text, id=name) for name, text in SEEN["talked_back"].items()],
)
def test_the_review_trees_non_briefs_are_rejected(text: str) -> None:
    assert unusable(text) == "talks-to-the-caller"


@pytest.mark.parametrize(
    "text",
    [pytest.param(text, id=name) for name, text in SEEN["written"].items()],
)
def test_real_briefs_still_pass(text: str) -> None:
    assert unusable(text) == ""


def test_the_first_person_of_an_acronym_is_not_a_speaker() -> None:
    text = (
        "The I/O layer buffers reads; you configure it with BUFSIZE, and the "
        "retry loop backs off on EAGAIN."
    )

    assert unusable(text) == ""
