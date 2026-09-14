"""T32: `hrono tree export` materializes the rendered tree to disk, safely."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.client.http import NoProfile

runner = CliRunner()


class FakeClient:
    def __init__(self, files: list[dict[str, str]]) -> None:
        self.files = files
        self.gets: list[str] = []

    def get(self, path: str) -> object:
        self.gets.append(path)
        return {"files": self.files}


def test_export_writes_the_folder_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeClient(
        [
            {"path": "root.md", "content": "ROOT"},
            {"path": "alpha-1/brief.md", "content": "ALPHA"},
            {"path": "alpha-1/sec-2.md", "content": "SECTION BODY"},
        ]
    )
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    out = tmp_path / "map"
    result = runner.invoke(
        cli.app, ["tree", "export", "acme", "-o", str(out), "--levels", "3"]
    )
    assert result.exit_code == 0
    assert fake.gets == ["/trees/acme/export?levels=3"]
    assert (out / "root.md").read_text() == "ROOT"
    assert (out / "alpha-1" / "brief.md").read_text() == "ALPHA"
    assert (out / "alpha-1" / "sec-2.md").read_text() == "SECTION BODY"
    assert "Wrote 3 files" in result.output


def test_export_refuses_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeClient([{"path": "../escape.md", "content": "EVIL"}])
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    out = tmp_path / "map"
    result = runner.invoke(cli.app, ["tree", "export", "acme", "-o", str(out)])
    assert result.exit_code == 1
    assert "outside" in result.output.lower()
    assert not (tmp_path / "escape.md").exists()  # nothing escaped


def test_export_no_profile_is_a_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_no_profile() -> object:
        raise NoProfile

    monkeypatch.setattr("hrono.tree.commands.from_profile", raise_no_profile)
    result = runner.invoke(
        cli.app, ["tree", "export", "acme", "-o", str(tmp_path / "m")]
    )
    assert result.exit_code == 1
    assert "profile" in result.output.lower()


def test_export_normalises_a_server_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # F19: 93 of 94 manifest paths came back with a leading slash, pathlib
    # rerooted the join, the guard refused the first entry and the command
    # wrote ZERO files. A leading slash now means "top of the export".
    fake = FakeClient(
        [
            {"path": "/benchmark-js-97.md", "content": "SECTION"},
            {"path": "/brief.md", "content": "BRIEF"},
            {"path": "root.md", "content": "ROOT"},
        ]
    )
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    out = tmp_path / "map"
    result = runner.invoke(cli.app, ["tree", "export", "acme", "-o", str(out)])
    assert result.exit_code == 0
    assert (out / "benchmark-js-97.md").read_text() == "SECTION"
    assert (out / "brief.md").read_text() == "BRIEF"
    assert (out / "root.md").read_text() == "ROOT"
    assert "Wrote 3 files" in result.output
    assert not (tmp_path.parent / "benchmark-js-97.md").exists()


def test_a_refused_entry_does_not_cost_the_whole_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeClient(
        [
            {"path": "../escape.md", "content": "EVIL"},
            {"path": "good.md", "content": "GOOD"},
            {"path": "../../also-escape.md", "content": "EVIL"},
        ]
    )
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    out = tmp_path / "map"
    result = runner.invoke(cli.app, ["tree", "export", "acme", "-o", str(out)])
    assert result.exit_code == 1
    assert (out / "good.md").read_text() == "GOOD"  # the safe file survived
    assert not (tmp_path / "escape.md").exists()
    assert "Wrote 1 file to" in result.output
    assert "refused 2 of 3" in result.output
