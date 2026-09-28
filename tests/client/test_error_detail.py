"""#197: the CLI threw away the only useful half of the server's error.

`hrono sources set` on a config with a missing field printed exactly two
words — "invalid body" — while the response carried the field and the reason.
A user could not learn the shape from the tool, and could not learn what they
had got wrong either.
"""

from __future__ import annotations

import httpx

from hrono.client.http import RequestFailed, _detail, message


def _response(payload: dict, status: int = 422) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_a_field_error_names_the_field_and_the_reason() -> None:
    answer = _detail(
        _response(
            {
                "error": {
                    "code": "validation-error",
                    "message": "invalid body",
                    "details": {
                        "errors": [
                            {"loc": ["git", "auth"], "msg": "Field required"}
                        ]
                    },
                }
            }
        )
    )

    assert "invalid body" in answer
    assert "git.auth: Field required" in answer


def test_every_field_error_is_shown_not_just_the_first() -> None:
    # a config with three things wrong should not need three round trips
    answer = _detail(
        _response(
            {
                "error": {
                    "message": "invalid body",
                    "details": {
                        "errors": [
                            {"loc": ["name"], "msg": "Field required"},
                            {"loc": ["type"], "msg": "Field required"},
                            {"loc": ["url"], "msg": "Field required"},
                        ]
                    },
                }
            }
        )
    )

    assert answer.count("Field required") == 3


def test_an_error_with_no_details_is_unchanged() -> None:
    answer = _detail(_response({"error": {"message": "not found"}}, 404))

    assert answer == "not found"


def test_a_detail_that_is_not_the_expected_shape_is_ignored() -> None:
    """A server that says something unexpected must not crash the CLI."""
    for details in ({"errors": "nonsense"}, {"other": 1}, "text", None):
        answer = _detail(
            _response({"error": {"message": "nope", "details": details}})
        )

        assert answer == "nope"


def test_a_field_error_with_no_location_still_says_something() -> None:
    answer = _detail(
        _response(
            {
                "error": {
                    "message": "invalid body",
                    "details": {"errors": [{"msg": "Unable to extract tag"}]},
                }
            }
        )
    )

    assert "body: Unable to extract tag" in answer


def test_the_rendered_message_carries_the_fields_through(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # `message()` is what the CLI actually prints, so the detail has to
    # survive the whole way out rather than only as far as `_detail`
    rendered = message(
        RequestFailed(422, "invalid body\n  git.auth: Field required")
    )

    assert "git.auth: Field required" in rendered
