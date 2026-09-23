"""#138: the CLI is a thin client — commands exist and address the server."""

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from hrono.cli import _bootstrap_message, app

runner = CliRunner()


class FakeClient:
    """Records the requests a command makes, so the wiring is observable."""

    def __init__(self, reply: object = None) -> None:
        self.reply = reply if reply is not None else {}
        self.calls: list[tuple[str, str, object]] = []

    def get(self, path: str) -> object:
        self.calls.append(("GET", path, None))
        return self.reply

    def post(self, path: str, body: dict[str, object]) -> object:
        self.calls.append(("POST", path, body))
        return self.reply

    def put(self, path: str, body: dict[str, object]) -> object:
        self.calls.append(("PUT", path, body))
        return self.reply

    def delete(self, path: str) -> object:
        self.calls.append(("DELETE", path, None))
        return self.reply


def _patch(monkeypatch: pytest.MonkeyPatch, module: str, client: FakeClient):
    monkeypatch.setattr(f"{module}.from_profile", lambda: client)
    return client


def test_tree_sync_posts_the_operator_verb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _patch(
        monkeypatch, "hrono.tree.commands", FakeClient({"job_id": "j1"})
    )

    result = runner.invoke(app, ["tree", "sync", "default"])

    assert result.exit_code == 0
    assert client.calls == [("POST", "/trees/default/sync", {})]
    assert "j1" in result.stdout


def test_the_lifecycle_stages_are_not_commands() -> None:
    # PO note D.2: stages must run in one order, and a wrong order produces a
    # map that looks right and is quietly wrong. They live behind an admin HTTP
    # door (#139), not a CLI verb anyone can reach for.
    listing = runner.invoke(app, ["tree", "--help"]).stdout

    for stage in ("propagate", "repair", "monitor", "settle", "update"):
        assert stage not in listing


@pytest.mark.parametrize(
    "collection", ["sources", "connections", "models", "prompts"]
)
def test_each_collection_has_the_four_config_commands(
    collection: str,
) -> None:
    # registering a source used to mean hand-written curl.
    listing = runner.invoke(app, [collection, "--help"]).stdout

    for command in ("list", "get", "set", "rm"):
        assert command in listing


def test_set_puts_the_config_so_it_creates_or_replaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _patch(monkeypatch, "hrono.registry.commands", FakeClient())
    config = tmp_path / "s.json"
    config.write_text(json.dumps({"name": "repo", "type": "git"}))

    result = runner.invoke(app, ["sources", "set", "repo", "-f", str(config)])

    assert result.exit_code == 0
    method, path, body = client.calls[0]
    assert (method, path) == ("PUT", "/sources/repo")
    assert body == {"name": "repo", "type": "git"}


def test_set_defaults_the_name_from_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _patch(monkeypatch, "hrono.registry.commands", FakeClient())
    config = tmp_path / "s.json"
    config.write_text(json.dumps({"type": "git"}))

    runner.invoke(app, ["sources", "set", "repo", "-f", str(config)])

    assert client.calls[0][2]["name"] == "repo"


def test_a_config_that_is_not_json_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch(monkeypatch, "hrono.registry.commands", FakeClient())
    config = tmp_path / "s.json"
    config.write_text("{not json")

    result = runner.invoke(app, ["sources", "set", "repo", "-f", str(config)])

    assert result.exit_code == 1
    assert "not valid JSON" in result.stderr  # a clean line, not a traceback
    assert "Traceback" not in result.stderr


def test_jobs_get_renders_what_the_run_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # one verb over six stages is only acceptable if the operator can find out
    # what happened (#132).
    client = _patch(
        monkeypatch,
        "hrono.jobs.commands",
        FakeClient(
            {
                "id": "j1",
                "op": "sync-tree",
                "status": "succeeded",
                "error": None,
                "result": {"judged": 3, "abstained": 1, "incomplete": True},
            }
        ),
    )

    result = runner.invoke(app, ["jobs", "get", "j1"])

    assert result.exit_code == 0
    assert client.calls == [("GET", "/jobs/j1", None)]
    assert "abstained" in result.stdout
    assert "true" in result.stdout.lower()


def test_jobs_get_says_so_when_nothing_was_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        "hrono.jobs.commands",
        FakeClient(
            {
                "id": "j2",
                "op": "embed",
                "status": "succeeded",
                "error": None,
                "result": None,
            }
        ),
    )

    result = runner.invoke(app, ["jobs", "get", "j2"])

    assert "none reported" in result.stdout


def test_the_bootstrap_hint_addresses_the_server_that_was_started() -> None:
    # served with --port 8299 it printed http://127.0.0.1:8080 — the one
    # copy-pasteable line in hrono's first run pointed at nothing.
    message = _bootstrap_message("tok", "0.0.0.0", 8299)

    assert "http://0.0.0.0:8299" in message
    assert "8080" not in message


def test_there_is_no_command_that_runs_a_single_stage() -> None:
    # #139: the service door is HTTP and admin-only, deliberately. A debugging
    # tool that looks like a product feature invites users to build workflows
    # on stages that are only safe in one order.
    top = runner.invoke(app, ["--help"]).stdout
    jobs = runner.invoke(app, ["jobs", "--help"]).stdout

    assert "run" not in jobs.split("Commands")[-1]
    for stage in ("propagate", "repair", "settle", "monitor"):
        assert stage not in top


def test_rm_says_whether_the_config_is_gone_or_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a seeded default is RESET rather than removed, and which happened is a
    # different thing for a user to know.
    deleted = _patch(
        monkeypatch, "hrono.registry.commands", FakeClient({"deleted": "x"})
    )
    gone = runner.invoke(app, ["prompts", "rm", "x"]).stdout
    assert deleted.calls == [("DELETE", "/prompts/x", None)]
    assert "Deleted" in gone

    _patch(
        monkeypatch, "hrono.registry.commands", FakeClient({"reset": "brief"})
    )
    reset = runner.invoke(app, ["prompts", "rm", "brief"]).stdout
    assert "Reset" in reset


def test_one_boundary_renders_every_cli_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # #048: six near-identical `_run` helpers rendered CLI errors, and #138
    # added two more while building the config CLI. Presentation is not each
    # command's business — commands raise, the boundary renders, and a command
    # body carries no error handling at all.
    from hrono.client.http import ClientError

    def boom() -> object:
        raise ClientError(401, {"error": {"message": "bad token"}})

    monkeypatch.setattr(
        "hrono.tree.commands.from_profile", lambda: _Raiser(boom)
    )

    result = runner.invoke(app, ["tree", "sync", "default"])

    assert result.exit_code == 1
    assert "Traceback" not in result.stderr
    assert result.stderr.strip()  # a line, not silence


class _Raiser:
    def __init__(self, fn: object) -> None:
        self.fn = fn

    def __getattr__(self, name: str) -> object:
        def call(*_args: object, **_kw: object) -> object:
            return self.fn()  # type: ignore[operator]

        return call


def test_a_command_body_has_no_error_handling() -> None:
    # the criterion that makes this stick: adding a command must require no new
    # error-handling boilerplate, so there must be none to copy.
    import inspect

    from hrono.jobs import commands as jobs_cmds
    from hrono.registry import commands as reg_cmds
    from hrono.tree import commands as tree_cmds

    for module in (tree_cmds, jobs_cmds, reg_cmds):
        source = inspect.getsource(module)
        assert "except ClientError" not in source
        assert "def _run(" not in source


def test_a_more_specific_renderer_wins_over_its_base() -> None:
    # the boundary's lookup is first-match by isinstance, so ORDER decides when
    # one entry subclasses another. No two entries are related today, so this
    # pins the RULE rather than a current behaviour — the next person to add a
    # subclass entry gets a failing test instead of a silent wrong message.
    from hrono.cli_boundary import RENDERERS, render

    class Base(Exception):
        pass

    class Specific(Base):
        pass

    ordered = {Specific: lambda _e: "specific", Base: lambda _e: "base"}
    with mock.patch.dict(RENDERERS, ordered, clear=True):
        assert render(Specific()) == "specific"
        assert render(Base()) == "base"


def test_an_error_the_table_does_not_know_is_not_rendered() -> None:
    # a boundary that renders everything would swallow real bugs into a
    # one-line message; anything unmapped must escape as itself.
    from hrono.cli_boundary import render

    assert render(RuntimeError("a genuine bug")) is None
