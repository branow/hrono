"""T28: the `hrono recall` CLI over the #010 client."""

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.client.http import NoProfile

runner = CliRunner()


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []
        self.timeouts: list[float | None] = []

    def post(
        self, path: str, body: dict, *, timeout: float | None = None
    ) -> object:
        # mirrors the real `Client.post`, keyword included: a stub whose
        # signature drifts from production stops testing the caller (#144)
        self.calls.append((path, body))
        self.timeouts.append(timeout)
        return self.payload


def test_recall_posts_and_prints_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(
        {
            "hits": [
                {
                    "uri": "git://ex/repo/a.py@v1",
                    "kind": "source",
                    "header": "git://ex/repo/a.py@v1",
                    "body": "the answer body",
                    "score": 0.9,
                }
            ],
            "message": None,
        }
    )
    monkeypatch.setattr("hrono.cli.from_profile", lambda: fake)
    result = runner.invoke(cli.app, ["recall", "acme", "how does auth work?"])
    assert result.exit_code == 0
    assert fake.calls == [
        ("/trees/acme/recall", {"question": "how does auth work?", "limit": 10})
    ]
    assert "the answer body" in result.output
    assert "[source]" in result.output


def test_recall_prints_the_explore_message_on_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient(
        {"hits": [], "message": "no confident matches - explore the map."}
    )
    monkeypatch.setattr("hrono.cli.from_profile", lambda: fake)
    result = runner.invoke(cli.app, ["recall", "acme", "nope", "--limit", "5"])
    assert result.exit_code == 0
    assert "explore the map" in result.output
    assert fake.calls[0][1]["limit"] == 5


def test_recall_no_profile_is_a_clean_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_no_profile() -> object:
        raise NoProfile

    monkeypatch.setattr("hrono.cli.from_profile", raise_no_profile)
    result = runner.invoke(cli.app, ["recall", "acme", "q"])
    assert result.exit_code == 1
    assert "profile" in result.output.lower()


def test_recall_asks_for_more_than_the_registry_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#168: 10s was the registry-CRUD default and a cold recall exceeds it.

    A warm server answers in milliseconds; a cold one reads the model's weights
    first, which measured 13.3s -- just over the default the CLI had inherited,
    so the read door failed and reported the server unreachable.
    """
    fake = FakeClient({"hits": [], "message": "nothing"})
    monkeypatch.setattr("hrono.cli.from_profile", lambda: fake)

    runner.invoke(cli.app, ["recall", "acme", "anything"])

    assert fake.timeouts == [cli.RECALL_TIMEOUT]
    assert cli.RECALL_TIMEOUT > 13.3
