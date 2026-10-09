import pytest

from hrono.summarize.faithfulness import faithfulness

SOURCE = (
    "The retryCount field defaults to 3. Call fetchUserProfile() to load the "
    "record. See src/api/handlers.py for the HttpClient wiring. Timeout is "
    "30000 ms."
)


def test_faithful_brief_has_no_unsupported_tokens() -> None:
    generated = (
        "This module exposes fetchUserProfile with a retryCount of 3, wired "
        "through HttpClient in src/api/handlers.py."
    )
    assert faithfulness(generated, SOURCE) == ()


def test_a_fabricated_identifier_is_caught() -> None:
    generated = "It also calls deleteAccount() and sets maxRetries to 999."
    missing = faithfulness(generated, SOURCE)
    assert "deleteAccount" in missing
    assert "maxRetries" in missing
    assert "999" in missing


def test_a_slash_compound_is_prose_not_an_identifier() -> None:
    # reading any slashed token as a name made 6 of 7 flags on a real test
    # corpus ordinary prose — CI/CD, tabs/spaces/line, binaries/packages.
    assert faithfulness("under api/handlers", SOURCE) == ()
    assert faithfulness("under api/ghost", SOURCE) == ()
    for prose in (
        "CI/CD",
        "and/or",
        "encoding/decoding",
        "licensor/contributors",
    ):
        assert faithfulness(f"it covers {prose} concerns", SOURCE) == ()


def test_case_insensitive_support() -> None:
    assert faithfulness("uses HTTPClient loosely", SOURCE) == ()


def test_plain_prose_is_not_flagged() -> None:
    assert (
        faithfulness("This is a normal sentence about records.", SOURCE) == ()
    )


def test_short_numbers_are_ignored_only_three_plus_digits_count() -> None:
    # "3" is short (ignored); "30000" is supported; "512" is fabricated
    assert faithfulness("caps at 512 items", SOURCE) == ("512",)


def test_result_is_sorted_and_deterministic() -> None:
    generated = "zeta_field and alpha_field and 7777 are new"
    assert faithfulness(generated, SOURCE) == (
        "7777",
        "alpha_field",
        "zeta_field",
    )


# eight tokens the gate flagged on real briefs of a test corpus: only
# Signer.rsplit is a genuine catch — the brief attributes a str.rsplit call to
# the Signer API — and the other seven are ordinary prose.
QA_SOURCE = (
    "continuous integration runs CI and CD jobs. tabs and line endings. "
    "the Signer class splits a signed value. TimedSerializer wraps loads and "
    "dumps. packages ship as binaries for contributors and every licensor. "
    "encoding helpers handle decoding too."
)


@pytest.mark.parametrize(
    "token",
    [
        "CI/CD",
        "tabs/spaces/line",
        "TimedSerializer.loads",
        "e.g",
        "binaries/packages",
        "licensor/contributors",
        "encoding/decoding",
    ],
)
def test_the_qa_false_positives_are_no_longer_flagged(token: str) -> None:
    assert faithfulness(f"the brief mentions {token} here", QA_SOURCE) == ()


def test_the_one_genuine_qa_catch_still_flags() -> None:
    assert faithfulness("Signer.rsplit is called", QA_SOURCE) == (
        "Signer.rsplit",
    )


def test_a_dotted_compound_is_supported_when_both_parts_are() -> None:
    # the source naming the receiver AND the member supports the combination;
    # a member that appears nowhere does not.
    assert faithfulness("call TimedSerializer.loads", QA_SOURCE) == ()
    assert faithfulness("call TimedSerializer.ghost", QA_SOURCE) == (
        "TimedSerializer.ghost",
    )
