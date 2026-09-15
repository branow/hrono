"""#103: the shape guard between the model and the stored tree."""

import pytest

from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.summarize.shape import answer, unusable

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
