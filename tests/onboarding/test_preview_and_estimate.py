"""What the setup path says a source holds and a build would cost.

The preview and the estimate are READS over the same files ingest reads, so
the tests that matter run the real sync and split ops over a real repository
and compare: the files the preview lists are the files ingest stored sections
for, and the sections the estimate counts are the sections the split stored.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database
from hrono.ingest import store
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync, sync_source
from hrono.onboarding import defaults, estimate
from hrono.onboarding.preview import preview
from hrono.registry import completeness
from hrono.registry import store as registry_store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from tests.context import job_context
from tests.ingest.test_split_op import FILES, job, make_repo, register

KEY = Fernet.generate_key()

JUNK = {
    "yarn.lock": "locked\n" * 40,
    "logo.svg": "<svg/>",
    "node_modules/dep/index.js": "module.exports = 1;\n",
    "notes/empty.md": "",
}


@pytest.fixture
def ingested(tmp_path: Path) -> Iterator[tuple[Database, Path]]:
    """A real repository, fetched and split by the real ops."""
    url = make_repo(tmp_path / "remote", {**FILES, **JUNK})
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    sync(job("sync", "repo"), job_context(db, tmp_path))
    split_source(job("split", "repo"), job_context(db, tmp_path))
    yield db, job_context(db, tmp_path).cache_for("repo")
    db.close()


def test_the_preview_lists_exactly_the_files_ingest_stored(
    ingested: tuple[Database, Path],
) -> None:
    db, cache = ingested

    shown = preview(cache, None)

    with db.connect() as conn:
        stored = {s["path"] for s in store.list_sections(conn, "repo")}
    assert {one.path for one in shown.kept} == stored
    assert stored == {"svc.py", "README.md", "data.json"}


def test_the_preview_follows_the_filter_as_ingest_does(
    tmp_path: Path,
) -> None:
    url = make_repo(tmp_path / "remote", {**FILES, **JUNK})
    db = Database.at(tmp_path / "hrono.db")
    flt = {"only": ["*.md"], "exclude": ["notes/**"]}
    with db.connect() as conn:
        registry_store.insert(
            conn,
            "sources",
            "repo",
            json.dumps(
                {
                    "name": "repo",
                    "type": "git",
                    "url": url,
                    "auth": {"method": "none"},
                    "filter": flt,
                }
            ),
            None,
            "t",
        )
    context = job_context(db, tmp_path)
    sync(job("sync", "repo"), context)
    split_source(job("split", "repo"), context)

    shown = preview(context.cache_for("repo"), flt)

    with db.connect() as conn:
        stored = {s["path"] for s in store.list_sections(conn, "repo")}
    assert {one.path for one in shown.kept} == stored == {"README.md"}
    db.close()


def test_the_preview_says_what_it_left_out_and_why(
    ingested: tuple[Database, Path],
) -> None:
    _, cache = ingested

    shown = preview(cache, None)

    left = {one.why: one.files for one in shown.refused}
    assert left == {
        "ignored by default: locks": 1,
        "ignored by default: assets": 1,
        "ignored by default: vendored": 1,
        "empty": 1,
    }
    locked = next(r for r in shown.refused if r.why.endswith("locks"))
    assert locked.bytes == len(JUNK["yarn.lock"])
    assert shown.bytes == sum(one.size for one in shown.kept)
    assert shown.largest[0].size == max(one.size for one in shown.kept)


def test_the_sections_counted_are_the_sections_the_split_stores(
    ingested: tuple[Database, Path],
) -> None:
    db, cache = ingested

    found = estimate.cut([(cache, None)])

    with db.connect() as conn:
        stored = store.list_sections(conn, "repo")
    assert found.sections == len(stored) > 3
    assert found.files == len({s["path"] for s in stored})


def test_the_fetch_the_setup_path_makes_is_the_one_a_sync_makes(
    tmp_path: Path,
) -> None:
    url = make_repo(tmp_path / "remote", FILES)
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    context = job_context(db, tmp_path)

    assert sync_source(context, "repo") == {"fetched": 1}
    assert sync_source(context, "repo") == {"fetched": 0}
    assert (context.cache_for("repo") / "svc.py").exists()
    db.close()


# ----------------------------------------------------------------- the cost


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    from hrono.db.database import open_database

    db = open_database(tmp_path / "hrono.db")
    record = reconcile(db, KEY)
    seed_defaults(db, Cipher.from_key(KEY, record.key_id), COLLECTIONS)
    yield db
    db.close()


def _register(conn: sqlite3.Connection, collection: str, **config: object):  # type: ignore[no-untyped-def]
    registry_store.insert(
        conn, collection, str(config["name"]), json.dumps(config), None, "t"
    )


def _models(conn: sqlite3.Connection, provider: str, **extra: object) -> None:
    _register(
        conn,
        "connections",
        name="c",
        provider=provider,
        auth={"method": "none"},
    )
    for role in ("condense", "brief", "brief-upper", "judge"):
        _register(
            conn,
            "models",
            name=role,
            kind="text",
            connection="c",
            role=role,
            model="m",
            **extra,
        )


CUT = estimate.Cut(files=3, sections=30, bytes=30 * 3500)
PRICE = {"input": 1.0, "output": 2.0, "cache_read": 0.0, "cache_write": 0.0}


def test_a_metered_build_is_priced_from_the_models_own_price(
    conn: sqlite3.Connection,
) -> None:
    _models(conn, "anthropic", price=PRICE)

    made = estimate.estimate(conn, CUT, width=4)

    by = {stage.role: stage for stage in made.stages}
    # 30 sections of 3500 B at 3.5 B/token: 1000 tokens, plus the prompt
    condense = by["condense"]
    template = len(
        json.loads(registry_store.get(conn, "prompts", "condense")["config"])[
            "template"
        ]
    )
    assert condense.calls == 30
    assert condense.input == 30 * (1000 + round(template / 3.5))
    assert condense.output == 30 * estimate.WRITTEN["api"]["condense"]
    assert condense.usd == pytest.approx(
        (condense.input * 1.0 + condense.output * 2.0) / 1e6
    )
    assert made.billed and not made.subscribed
    assert made.metered == pytest.approx(
        sum(s.usd for s in made.stages if s.usd is not None), abs=1e-4
    )
    assert made.subscription == 0.0


def test_topics_follow_the_measured_size_of_a_topic(
    conn: sqlite3.Connection,
) -> None:
    _models(conn, "anthropic", price=PRICE)

    made = estimate.estimate(conn, CUT, width=4)

    by = {stage.role: stage for stage in made.stages}
    # 30 sections at 15 a topic is 2 leaf topics, grouped under 1 root
    assert by["brief"].calls == 2
    assert by["brief-upper"].calls == 1
    assert made.calls == 33


def test_a_subscription_is_an_estimate_and_never_added_to_spend(
    conn: sqlite3.Connection,
) -> None:
    _models(conn, "claude-code", price=PRICE)

    made = estimate.estimate(conn, CUT, width=4)

    assert made.subscribed and not made.billed
    assert made.subscription and made.subscription > 0
    assert made.metered == 0.0
    condense = made.stages[0]
    assert condense.output == 30 * estimate.WRITTEN["claude-code"]["condense"]
    # the harness every call carries is part of what it reads
    assert condense.input > 30 * (estimate.HARNESS_READ)


def test_a_model_the_price_table_does_not_know_makes_the_cost_unknown(
    conn: sqlite3.Connection,
) -> None:
    _models(conn, "anthropic")

    made = estimate.estimate(conn, CUT, width=4)

    assert made.metered is None
    assert made.unpriced == ("m",)


def test_an_alias_is_priced_as_the_model_the_provider_said_it_ran(
    conn: sqlite3.Connection,
) -> None:
    _models(conn, "anthropic")
    conn.execute(
        "INSERT INTO llm_calls (model, role, provider, upstream_model, "
        "duration_ms, ok, created_at) VALUES "
        "('condense', 'validate', 'anthropic', 'claude-haiku-4-5-2025', "
        "1, 1, 't')"
    )

    made = estimate.estimate(conn, CUT, width=4)

    by = {stage.role: stage for stage in made.stages}
    assert by["condense"].usd is not None
    assert by["brief"].usd is None


def test_more_calls_at_once_take_less_time(conn: sqlite3.Connection) -> None:
    _models(conn, "anthropic", price=PRICE)

    narrow = estimate.estimate(conn, CUT, width=1)
    wide = estimate.estimate(conn, CUT, width=8)

    assert narrow.seconds > wide.seconds
    assert wide.seconds >= estimate.FIXED_SECONDS


def test_the_shipped_defaults_make_a_registry_a_build_accepts(
    conn: sqlite3.Connection,
) -> None:
    """The rows setup registers are exactly what `completeness` asks for."""
    for chosen in defaults.PROVIDERS:
        for table in ("models", "connections", "sources"):
            conn.execute("DELETE FROM registry WHERE collection = ?", (table,))
        _register(conn, "sources", name="s", type="git", url="x", auth={})
        _register(
            conn,
            "connections",
            name="c",
            provider=chosen.name,
            auth={"method": "none"},
        )
        for one in defaults.models_for(chosen.name, "c"):
            _register(conn, "models", **one)

        assert completeness.gaps(conn) == (), chosen.name


def test_a_provider_setup_does_not_know_gets_rows_with_no_model_id() -> None:
    rows = defaults.models_for("openai", "c")

    assert [r["model"] for r in rows if r["kind"] == "text"] == [""] * 4


def test_the_estimate_agrees_with_a_measured_build_within_a_quarter(
    conn: sqlite3.Connection,
) -> None:
    """What `chalk` really cost, against what the estimate said before it.

    A real claude-code build of a 26-file repository (27 sections, 62,513 B):
    30 calls, 484,818 tokens read, 30,288 written, 151 s, and $0.4252 at the
    API's prices, taken from its ledger. The constants were fitted on another
    repository, so this is a held-out build, and it pins them: moving one so
    the estimate leaves this range fails here rather than on someone's bill.
    """
    _models(conn, "claude-code")
    for model, upstream in (
        ("condense", "claude-haiku-4-5-20251001"),
        ("brief", "claude-sonnet-5-5"),
        ("brief-upper", "claude-sonnet-5-5"),
    ):
        conn.execute(
            "INSERT INTO llm_calls (model, role, provider, upstream_model, "
            "duration_ms, ok, created_at) VALUES (?, 'validate', "
            "'claude-code', ?, 1, 1, 't')",
            (model, upstream),
        )
    measured = {
        "calls": 30,
        "input": 484_818,
        "output": 30_288,
        "seconds": 151,
        "usd": 0.4252,
    }

    made = estimate.estimate(
        conn, estimate.Cut(files=26, sections=27, bytes=62_513), width=4
    )

    said = {
        "calls": made.calls,
        "input": made.input,
        "output": made.output,
        "seconds": made.seconds,
        "usd": made.subscription,
    }
    for key, real in measured.items():
        assert said[key] == pytest.approx(real, rel=0.25), key
