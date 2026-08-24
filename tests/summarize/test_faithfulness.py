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


def test_slash_compound_supported_when_every_part_is() -> None:
    # "api/handlers" — both parts appear in source -> supported
    assert faithfulness("under api/handlers", SOURCE) == ()
    # "api/ghost" — ghost is absent -> flagged
    assert "api/ghost" in faithfulness("under api/ghost", SOURCE)


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
