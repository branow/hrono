"""`hrono tree export` materializes the rendered tree to disk, safely."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.client.http import NoProfile
from hrono.tree.commands import _materialize, _refusal

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
    # a leading slash means "top of the export": manifest paths may carry
    # one, and taken literally pathlib reroots the join, the guard refuses
    # the entry and the command writes nothing.
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


@pytest.mark.parametrize("degenerate", ["/", ".", "", "..", "/../"])
def test_a_path_resolving_onto_the_output_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, degenerate: str
) -> None:
    # such a path maps onto `out` itself, which is a DIRECTORY: it must not
    # pass the guard, because IsADirectoryError out of the command would lose
    # every entry after it with no "Wrote"/"refused" line at all.
    fake = FakeClient(
        [
            {"path": "a.md", "content": "A"},
            {"path": degenerate, "content": "DEGENERATE"},
            {"path": "b.md", "content": "B"},
        ]
    )
    monkeypatch.setattr("hrono.tree.commands.from_profile", lambda: fake)
    out = tmp_path / "map"
    result = runner.invoke(cli.app, ["tree", "export", "acme", "-o", str(out)])
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    assert (out / "a.md").read_text() == "A"
    assert (out / "b.md").read_text() == "B"  # not lost to the bad entry
    assert out.is_dir()  # the output directory itself was never written over
    assert "Wrote 2 files" in result.output
    assert "refused 1 of 3" in result.output


def test_a_directory_collision_costs_only_its_own_entry(tmp_path: Path) -> None:
    # `alpha-1/brief.md` makes `alpha-1` a directory, so writing `alpha-1`
    # as a FILE raises IsADirectoryError. An unguarded loop would lose every
    # entry after it and skip the report entirely — the same shape the
    # output-path guard removes, one layer down.
    files = [
        {"path": "alpha-1/brief.md", "content": "first"},
        {"path": "alpha-1", "content": "the collision"},
        {"path": "beta-2.md", "content": "after the failure"},
    ]

    written, refused = _materialize(tmp_path / "out", files)

    assert written == 2
    assert [r.path for r in refused] == ["alpha-1"]
    assert [r.reason for r in refused] == ["collides"]
    # the entry AFTER the failure was still attempted
    assert (tmp_path / "out" / "beta-2.md").read_text() == "after the failure"


def test_a_file_blocking_a_directory_costs_only_its_own_entry(
    tmp_path: Path,
) -> None:
    # the mirror: `a.md` is a file, so `a.md/b.md` cannot be created under it.
    files = [
        {"path": "a.md", "content": "first"},
        {"path": "a.md/b.md", "content": "blocked"},
        {"path": "c.md", "content": "after"},
    ]

    written, refused = _materialize(tmp_path / "out", files)

    assert written == 2
    assert [r.path for r in refused] == ["a.md/b.md"]
    assert (tmp_path / "out" / "c.md").exists()


def test_the_refusal_message_says_which_kind_each_was(
    tmp_path: Path,
) -> None:
    # saying every refusal "would write outside" the folder is untrue of a
    # collision (inside it) and of a degenerate path (onto it), and would tell
    # a user something false about their own data.
    files = [
        {"path": "alpha-1/brief.md", "content": "first"},
        {"path": "alpha-1", "content": "collides"},
        {"path": "../escape.md", "content": "escapes"},
    ]

    _written, refused = _materialize(tmp_path / "out", files)
    message = _refusal(tmp_path / "out", len(files), refused)

    assert "collide with a path already written under" in message
    assert "write outside" in message
    assert "refused 2 of 3" in message


def _export(
    out: Path, monkeypatch: pytest.MonkeyPatch, files: list[dict[str, str]]
) -> object:
    monkeypatch.setattr(
        "hrono.tree.commands.from_profile", lambda: FakeClient(files)
    )
    return runner.invoke(
        cli.app, ["tree", "export", "acme", "-o", str(out), "--replace"]
    )


def test_replace_drops_pages_the_new_export_no_longer_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "map"
    out.mkdir()
    (out / "root.md").write_text("OLD ROOT")
    (out / "retired-7").mkdir()
    (out / "retired-7" / "brief.md").write_text("A TOPIC THAT IS GONE")

    result = _export(out, monkeypatch, [{"path": "root.md", "content": "NEW"}])

    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert (out / "root.md").read_text() == "NEW"
    assert not (out / "retired-7").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["map"]  # no leftovers


def test_replace_refuses_a_folder_that_is_not_an_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "project"
    out.mkdir()
    (out / "main.py").write_text("print('mine')")

    result = _export(out, monkeypatch, [{"path": "root.md", "content": "NEW"}])

    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert "no root.md" in result.output  # type: ignore[attr-defined]
    assert (out / "main.py").read_text() == "print('mine')"
    assert not (out / "root.md").exists()
