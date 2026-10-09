"""From an empty install to a built tree, in the browser.

The server is the production app over a database file it owns, so its cache
root, its seeded prompts and its worker are the real ones (the worker is
stopped: starting a build must be asserted as a queued job, not run). The
remote is a real git repository; the provider's answer to a wrong key comes
from a real HTTP server through the connection's own endpoint field. Only the
two calls that need a model are stood in for — one trivial question to a text
model, one embedding — because those are what a test cannot pay for.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed import runner
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import completeness
from hrono.registry import store as registry_store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from hrono.registry.validation import connection_validation, model_validation
from hrono.server.app import create_app
from tests.server.repo import commit, make_repo
from tests.stub_server import serving

KEY = Fernet.generate_key()
TREE = "default"


class Setup:
    def __init__(self, client: TestClient, tokens: dict, root: Path) -> None:
        self.client = client
        self.tokens = tokens
        self.root = root
        self.probes: list[str] = []

    def sign_in(self, role: str = "admin") -> None:
        self.client.cookies.clear()
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def page(self, step: str = "", **query: str) -> str:
        params = {"tree": TREE, **({"step": step} if step else {}), **query}
        return self.client.get("/ui/setup", params=params).text

    def post(self, path: str, **data: str):  # type: ignore[no-untyped-def]
        return self.client.post(
            path, data={"tree": TREE, **data}, follow_redirects=False
        )

    def rows(self, collection: str) -> list[str]:
        with self.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
            return [
                str(r["name"])
                for r in registry_store.list_all(conn, collection)
            ]

    def gaps(self) -> tuple[completeness.Gap, ...]:
        with self.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
            return completeness.gaps(conn)

    def connect_claude_code(self) -> None:
        self.post(
            "/ui/setup/connection",
            variant="claude-code",
            **{"f.name": "cc", "f.auth.method": "none"},
        )

    def register_models(self) -> None:
        self.post(
            "/ui/setup/models",
            connection="cc",
            embedding="some/embedder",
            condense="haiku",
            brief="sonnet",
            **{"brief-upper": "sonnet", "judge": "haiku"},
        )

    def add_source(self, url: str, **extra: str):  # type: ignore[no-untyped-def]
        return self.post(
            "/ui/setup/source",
            variant="git",
            **{
                "f.name": "repo",
                "f.url": url,
                "f.auth.method": "none",
                **extra,
            },
        )


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Setup]:
    path = tmp_path / "hrono.db"
    conn = open_database(path)
    record = reconcile(conn, KEY)
    seed_defaults(conn, Cipher.from_key(KEY, record.key_id), COLLECTIONS)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    conn.close()
    monkeypatch.setattr(connection_validation, "_cli_version", lambda: True)
    app = create_app(db_path=path, master_key=KEY)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        made = Setup(client, tokens, tmp_path)

        def embed(*_: object) -> list[float]:
            made.probes.append("embedding")
            return [0.0] * 4

        def ask(config: dict, context: object, timeout: float) -> str:
            made.probes.append(str(config["name"]))
            return "ok"

        monkeypatch.setattr(runner, "backend_installed", lambda: True)
        monkeypatch.setattr(model_validation, "_default_embed", embed)
        monkeypatch.setattr(model_validation, "_generate_with_cli", ask)
        made.sign_in()
        yield made


def text(page: str) -> str:
    """What a person reads: the page without its markup."""
    body = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    made = make_repo(tmp_path / "remote")
    (made / "app.py").write_text("def run():\n    return 1\n" * 40)
    (made / "yarn.lock").write_text("x\n" * 50)
    (made / "logo.svg").write_text("<svg/>")
    commit(made, "two")
    return made


# ------------------------------------------------------------------- the path


def test_a_new_install_opens_at_the_connection_step(setup: Setup) -> None:
    page = setup.page()

    assert 'id="step-connection"' in page
    for label in ("Connection", "Models", "Source", "Estimate and build"):
        assert label in text(page)


def test_each_provider_has_its_trade_off_in_two_sentences(
    setup: Setup,
) -> None:
    for provider in ("claude-code", "anthropic"):
        page = setup.page("connection", provider=provider, change="1")
        said = re.search(r'id="trade-off">(.*?)</p>', page, flags=re.S)

        assert said is not None
        assert len(re.findall(r"[.!?](?:\s|$)", said.group(1))) == 2, provider
    assert "API key" in text(setup.page("connection", provider="anthropic"))


def test_a_step_is_not_open_until_the_ones_before_it_are_done(
    setup: Setup,
) -> None:
    assert 'id="step-connection"' in setup.page("build")
    assert 'id="step-connection"' in setup.page("source")


def test_the_whole_path_from_nothing_to_an_estimate(
    setup: Setup, repo: Path
) -> None:
    # 1: a connection
    moved = setup.post(
        "/ui/setup/connection",
        variant="claude-code",
        **{"f.name": "cc", "f.auth.method": "none"},
    )
    assert (
        moved.status_code == 303 and "step=models" in moved.headers["location"]
    )
    assert setup.rows("connections") == ["cc"]
    assert 'id="step-models"' in setup.page()

    # 2: models, one per role, each asked one question before it was stored
    moved = setup.post(
        "/ui/setup/models",
        connection="cc",
        embedding="some/embedder",
        condense="haiku",
        brief="sonnet",
        **{"brief-upper": "sonnet", "judge": "haiku"},
    )
    assert "step=source" in moved.headers["location"]
    assert sorted(setup.rows("models")) == sorted(
        ["embedder", "condense", "brief", "brief-upper", "judge"]
    )
    assert sorted(setup.probes) == sorted(
        ["embedding", "condense", "brief", "brief-upper", "judge"]
    )
    assert 'id="step-source"' in setup.page()

    # 3: a source, fetched, with a preview
    moved = setup.add_source(str(repo))
    assert "step=source&source=repo" in moved.headers["location"]
    shown = text(setup.page("source", source="repo"))
    assert "files would be read" in shown
    assert "ignored by default: locks" in shown
    assert "ignored by default: assets" in shown

    # 4: an estimate, over the sections the files cut into
    estimate = text(setup.page("build"))
    assert re.search(r"about \d+ model calls over \d+ sections", estimate)
    assert "estimate and not spend" in estimate
    assert setup.gaps() == ()


# --------------------------------------------------------------- a wrong key


def test_models_step_without_the_embed_backend_says_how_to_get_it(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup.connect_claude_code()
    monkeypatch.setattr(runner, "backend_installed", lambda: False)

    page = setup.page("models")

    assert "uv pip install" in page and "hrono[embed]" in page
    assert 'action="/ui/setup/models"' not in page
    assert 'id="step-models"' in page
    assert "remote embedding model instead" in page
    assert 'section=models">Settings</a>' in page


def test_models_step_with_the_embed_backend_offers_the_form(
    setup: Setup,
) -> None:
    setup.connect_claude_code()

    page = setup.page("models")

    assert 'action="/ui/setup/models"' in page
    assert "hrono[embed]" not in page


def test_a_wrong_key_is_refused_with_the_providers_reason_and_saves_nothing(
    setup: Setup,
) -> None:
    class Rejects(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = (
                b'{"type":"error","error":{"type":"authentication_error",'
                b'"message":"invalid x-api-key"}}'
            )
            self.send_response(401)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return

    with serving(Rejects) as base:
        answer = setup.client.post(
            "/ui/setup/connection",
            data={
                "tree": TREE,
                "variant": "anthropic",
                "f.name": "anthropic",
                "f.auth.method": "api-key",
                "f.auth.key": "not-a-real-key",
                "f.endpoint": base,
            },
            follow_redirects=False,
        )

    assert answer.status_code == 200
    assert "authentication failed: invalid x-api-key" in text(answer.text)
    assert setup.rows("connections") == []
    assert 'id="step-connection"' in setup.page("models")


# ----------------------------------------------------------- stopping halfway


def test_models_that_failed_midway_leave_valid_rows_and_are_not_asked_twice(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup.connect_claude_code()
    real = model_validation._generate_with_cli

    def refuse_brief(config: dict, context: object, timeout: float) -> str:
        if config["name"] == "brief-upper":
            raise model_validation.ValidationFailed("overloaded")
        return real(config, context, timeout)

    monkeypatch.setattr(model_validation, "_generate_with_cli", refuse_brief)

    answer = setup.post(
        "/ui/setup/models",
        connection="cc",
        embedding="some/embedder",
        condense="haiku",
        brief="sonnet",
        **{"brief-upper": "sonnet", "judge": "haiku"},
    )

    assert answer.status_code == 200
    assert "brief-upper: overloaded" in text(answer.text)
    assert sorted(setup.rows("models")) == ["brief", "condense", "embedder"]
    assert setup.probes == ["embedding", "condense", "brief"]
    # what is stored is valid config, and the page knows what is still missing
    assert "models" in {gap.section for gap in setup.gaps()}
    assert 'id="step-models"' in setup.page()

    monkeypatch.setattr(model_validation, "_generate_with_cli", real)
    setup.probes.clear()
    setup.register_models()

    assert setup.probes == ["brief-upper", "judge"]
    assert [g.section for g in setup.gaps()] == ["sources"]


def test_stopping_before_the_build_leaves_no_tree_and_no_job(
    setup: Setup, repo: Path
) -> None:
    setup.connect_claude_code()
    setup.register_models()
    setup.add_source(str(repo))

    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        topics = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert (topics, jobs) == (0, 0)
    assert setup.gaps() == ()


def test_a_source_that_cannot_be_reached_is_refused_and_not_stored(
    setup: Setup, tmp_path: Path
) -> None:
    setup.connect_claude_code()
    setup.register_models()

    answer = setup.add_source(str(tmp_path / "nowhere"))

    assert answer.status_code == 200
    assert "cannot reach repository" in text(answer.text)
    assert setup.rows("sources") == []


def test_a_source_that_vanishes_after_saving_says_it_could_not_be_read(
    setup: Setup, repo: Path
) -> None:
    setup.connect_claude_code()
    setup.register_models()
    setup.add_source(str(repo))
    (repo / ".git").rename(repo.parent / "moved-git")

    answer = setup.post("/ui/setup/source/fetch", name="repo")

    assert answer.status_code == 200
    assert "could not be read" in text(answer.text)


# ------------------------------------------------------------------ the build


def _ready(setup: Setup, repo: Path) -> None:
    setup.connect_claude_code()
    setup.register_models()
    setup.add_source(str(repo))


def test_building_queues_the_first_run_and_lands_on_it(
    setup: Setup, repo: Path
) -> None:
    _ready(setup, repo)

    moved = setup.post("/ui/setup/build")

    location = moved.headers["location"]
    assert moved.status_code == 303 and location.startswith("/ui/jobs/job_")
    job = location.split("/ui/jobs/")[1].split("?")[0]
    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        row = conn.execute(
            "SELECT op, tree, started_by FROM jobs WHERE id = ?", (job,)
        ).fetchone()
    assert (row["op"], row["tree"], row["started_by"]) == (
        "maintain",
        TREE,
        "admin",
    )


def test_building_an_unregistered_tree_is_refused_and_queues_nothing(
    setup: Setup, repo: Path
) -> None:
    _ready(setup, repo)

    refused = setup.post("/ui/setup/build", tree="nope")

    assert refused.status_code == 200
    assert 'id="step-build"' in refused.text
    assert "tree not registered: nope" in refused.text
    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0


def test_pressing_build_twice_does_not_start_a_second_run(
    setup: Setup, repo: Path
) -> None:
    _ready(setup, repo)

    first = setup.post("/ui/setup/build").headers["location"]
    second = setup.post("/ui/setup/build").headers["location"]

    assert first == second
    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_a_build_is_refused_while_a_step_is_open(
    setup: Setup, repo: Path
) -> None:
    setup.connect_claude_code()

    moved = setup.post("/ui/setup/build")

    assert "step=models" in moved.headers["location"]
    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_a_tree_that_is_built_offers_a_sync_not_a_second_build(
    setup: Setup, repo: Path
) -> None:
    _ready(setup, repo)
    with setup.client.app.state.db.write() as conn:  # type: ignore[attr-defined]
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )

    page = setup.page("build")

    assert "already built" in page
    assert f'action="/ui/trees/{TREE}/sync"' in page
    assert "/ui/setup/build" not in page


# ---------------------------------------------------------------------- roles


def test_a_reader_sees_where_things_stand_and_cannot_change_them(
    setup: Setup, repo: Path
) -> None:
    setup.sign_in("reader")

    page = setup.page()

    assert "needs an account that can write" in text(page)
    assert '<form class="item-form"' not in page
    refused = setup.post("/ui/setup/connection", variant="claude-code")
    assert refused.status_code in (303, 307, 403)
    assert setup.rows("connections") == []


@pytest.mark.parametrize(
    "path", ["connection", "models", "source", "source/fetch", "build"]
)
def test_every_write_refuses_a_reader(setup: Setup, path: str) -> None:
    setup.sign_in("reader")

    answer = setup.post(f"/ui/setup/{path}")

    assert answer.status_code != 200
    assert setup.rows("connections") == setup.rows("sources") == []


# -------------------------------------------------------- the way in and out


def test_an_empty_home_leads_a_writer_into_setup(setup: Setup) -> None:
    page = setup.client.get(f"/ui?tree={TREE}").text

    assert 'id="setup-link"' in page
    assert "Set up and build" in text(page)


def test_home_says_to_continue_once_something_is_set_up(setup: Setup) -> None:
    setup.connect_claude_code()

    page = setup.client.get(f"/ui?tree={TREE}").text

    assert "Continue setting up" in text(page)


def test_a_reader_is_not_offered_setup_on_home(setup: Setup) -> None:
    setup.sign_in("reader")

    assert 'id="setup-link"' not in setup.client.get(f"/ui?tree={TREE}").text


def test_no_step_tells_anyone_to_open_a_terminal(
    setup: Setup, repo: Path
) -> None:
    pages = [
        setup.page("connection"),
        setup.page("connection", provider="anthropic"),
    ]
    setup.connect_claude_code()
    pages.append(setup.page("models"))
    setup.register_models()
    pages.append(setup.page("source"))
    setup.add_source(str(repo))
    pages += [setup.page("source", source="repo"), setup.page("build")]

    for page in pages:
        shown = text(page.split("<main", 1)[1]).lower()
        for word in ("terminal", "open a shell", "type ", "run hrono"):
            assert word not in shown, word
        assert not re.search(r"hrono (serve|tree|profile|admin|sources)", shown)


def test_a_model_this_path_did_not_register_is_left_for_settings(
    setup: Setup,
) -> None:
    setup.connect_claude_code()
    with setup.client.app.state.db.write() as conn:  # type: ignore[attr-defined]
        registry_store.insert(
            conn,
            "models",
            "mine",
            json.dumps(
                {
                    "name": "mine",
                    "kind": "text",
                    "connection": "cc",
                    "model": "m",
                    "role": "condense",
                }
            ),
            None,
            "t",
        )

    page = setup.page("models")

    assert "not enough to build" in text(page)
    assert 'action="/ui/setup/models"' not in page


def test_a_built_homes_load_does_not_ask_what_setup_lacks(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check walks every resolver, so only an EMPTY tree pays for it."""
    from hrono.server.ui import setup as ui_setup

    asked: list[int] = []

    def counting(conn: object) -> tuple[()]:
        asked.append(1)
        return ()

    monkeypatch.setattr(ui_setup.completeness, "gaps", counting)
    setup.client.get(f"/ui?tree={TREE}")
    assert asked, "an empty tree should ask"
    asked.clear()
    with setup.client.app.state.db.write() as conn:  # type: ignore[attr-defined]
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )

    setup.client.get(f"/ui?tree={TREE}")

    assert asked == []


# ------------------------------------------- a source's own filter, and syncing


def _context(setup: Setup) -> JobContext:
    state = setup.client.app.state  # type: ignore[attr-defined]
    return JobContext(state.db, state.cipher, cache_root=state.cache_root)


def _job(name: str) -> SimpleNamespace:
    return SimpleNamespace(scope={"name": name})


def test_the_preview_and_estimate_use_the_sources_own_filter(
    setup: Setup, repo: Path
) -> None:
    (repo / "docs.md").write_text("# one\ntext\n\n# two\nmore\n" * 30)
    commit(repo, "three")
    setup.connect_claude_code()
    setup.register_models()
    setup.add_source(str(repo), **{"f.filter.only": "app.py"})

    shown = text(setup.page("source", source="repo"))
    estimate = text(setup.page("build"))

    # what the real sync and split keep for this source
    context = _context(setup)
    OPS["sync"](_job("repo"), context)  # type: ignore[arg-type]
    OPS["split"](_job("repo"), context)  # type: ignore[arg-type]
    with setup.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        files = conn.execute(
            "SELECT COUNT(DISTINCT path) FROM sections WHERE source = 'repo'"
        ).fetchone()[0]
        stored = conn.execute(
            "SELECT COUNT(*) FROM sections WHERE source = 'repo'"
        ).fetchone()[0]
    assert files == 1 and stored > 0
    assert f"{files} file would be read" in shown
    assert f"over {stored} sections" in estimate


def test_the_first_build_after_setup_still_fetches_the_source(
    setup: Setup, repo: Path
) -> None:
    _ready(setup, repo)  # the wizard has already fetched the cache

    first = OPS["sync"](_job("repo"), _context(setup))  # type: ignore[arg-type]
    again = OPS["sync"](_job("repo"), _context(setup))  # type: ignore[arg-type]

    assert dict(first) == {"fetched": 1}
    assert dict(again) == {"fetched": 0}


def test_a_source_name_with_query_syntax_stays_one_value(
    setup: Setup, repo: Path
) -> None:
    setup.connect_claude_code()
    setup.register_models()

    moved = setup.post(
        "/ui/setup/source",
        variant="git",
        **{
            "f.name": "x&source=repo",
            "f.url": str(repo),
            "f.auth.method": "none",
        },
    )

    query = parse_qs(urlparse(moved.headers["location"]).query)
    assert query["source"] == ["x&source=repo"]
