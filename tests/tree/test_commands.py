import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.client.http import NoProfile

runner = CliRunner()


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, body: dict) -> object:
        self.calls.append((path, body))
        return {"job_id": "job_abc"}


def test_maintain_posts_and_prints_the_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient()
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    result = runner.invoke(cli.app, ["tree", "maintain", "acme"])
    assert result.exit_code == 0
    assert fake.calls == [("/trees/acme/maintain", {})]
    assert "job_abc" in result.output


def test_no_profile_is_a_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_no_profile() -> object:
        raise NoProfile

    monkeypatch.setattr("hrono.tree.commands.from_profile", raise_no_profile)
    result = runner.invoke(cli.app, ["tree", "maintain", "acme"])
    assert result.exit_code == 1
    assert "profile" in result.output.lower()


class FakePoolClient:
    def __init__(self, pool: list[dict[str, object]]) -> None:
        self.pool = pool
        self.calls: list[str] = []

    def get(self, path: str) -> object:
        self.calls.append(path)
        return {"count": len(self.pool), "pending": self.pool}


def test_pending_lists_the_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePoolClient(
        [{"content_hash": "ab", "path": "docs/stranded.md", "batch": 4}]
    )
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    result = runner.invoke(cli.app, ["tree", "pending", "acme"])
    assert result.exit_code == 0
    assert fake.calls == ["/trees/acme/pending"]
    assert "docs/stranded.md" in result.output
    assert "1 pending chunks" in result.output
