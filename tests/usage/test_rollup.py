"""#202: the ledger rolled up — per run, model, user, day — with honest cost."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import enqueue
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.llm.ledger import Ledgered, metered
from hrono.registry import store as registry_store
from hrono.registry.collections.models import Model
from hrono.server.app import create_app
from hrono.tree.maintain import maintain
from hrono.usage.prices import PRICES, price_for
from hrono.usage.rollup import EVERYTHING, Filter, for_jobs, usage
from tests.context import job_context
from tests.tree.test_maintain import (
    fake_build,
    fake_encoder,
    job,
    make_repo,
    register,
)

UPSTREAM = "claude-sonnet-5-20260101"
SONNET = PRICES["claude-sonnet-5"]
USAGE = Usage(10, 4, cache_read=2, cache_creation=3, model=UPSTREAM)


class Reporting:
    """A completion that reports what a real provider reports."""

    def __init__(self, usage: Usage = USAGE) -> None:
        self.calls = 0
        self._usage = usage

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
            self._usage,
        )


def built(
    database: Database, tmp_path: Path, client: Reporting
) -> tuple[str, Reporting]:
    """A REAL multi-stage run — maintain, through the ledger's own writer."""
    run_id = enqueue(database, "maintain", {}, tree="default", started_by="ana")
    context = job_context(database, tmp_path)
    maintain(
        job(),
        JobContext(context.database, None, context.cache_root, run_id),
        encoder_for=fake_encoder,
        client=client,
        build=fake_build,
    )
    return run_id, client


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo")
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    yield database
    database.close()


def _by(database: Database, by: str, where: Filter = EVERYTHING) -> list[dict]:
    with database.connect() as conn:
        return usage(conn, by, where)


def _sonnet_cost(calls: int) -> float:
    return calls * SONNET.cost(10, 4, 2, 3)


def test_a_run_adds_up_every_call_its_stages_made(
    db: Database, tmp_path: Path
) -> None:
    run_id, client = built(db, tmp_path, Reporting())

    [group] = _by(db, "run")

    with db.connect() as conn:
        batches = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE role = 'embedding'"
        ).fetchone()[0]
    assert client.calls > 3 and batches > 0  # condense, brief, brief-upper
    assert group["key"] == run_id
    assert group["calls"] == client.calls + batches
    assert group["tokens"] == {
        "input": 10 * client.calls,
        "output": 4 * client.calls,
        "cache_read": 2 * client.calls,
        "cache_creation": 3 * client.calls,
    }
    assert group["cost"]["metered"] == {
        "usd": round(_sonnet_cost(client.calls), 6),
        "unpriced": [],
    }
    assert group["cost"]["billing"] == ["local", "metered"]
    assert group["run"]["started_by"] == "ana"
    assert group["run"]["op"] == "maintain"


@pytest.mark.parametrize(
    ("by", "keys"),
    [
        pytest.param("model", {"sonnet", "emb"}, id="configured-model"),
        pytest.param("upstream-model", {UPSTREAM, "fake"}, id="upstream"),
        pytest.param("user", {"ana"}, id="user"),
    ],
)
def test_each_grouping_splits_the_same_calls(
    db: Database, tmp_path: Path, by: str, keys: set[str]
) -> None:
    _, client = built(db, tmp_path, Reporting())

    groups = _by(db, by)

    assert {g["key"] for g in groups} == keys
    assert sum(g["calls"] for g in groups) == sum(
        g["calls"] for g in _by(db, "run")
    )
    assert sum(g["tokens"]["output"] for g in groups) == 4 * client.calls


def test_by_day_keys_on_the_calendar_day(db: Database, tmp_path: Path) -> None:
    built(db, tmp_path, Reporting())

    [group] = _by(db, "day")

    assert group["key"] == datetime.now(UTC).date().isoformat()
    assert group["model_seconds"] >= 0


def test_a_model_with_no_known_price_is_unknown_and_named(
    db: Database, tmp_path: Path
) -> None:
    built(db, tmp_path, Reporting(Usage(10, 4, model="mystery-1")))

    [group] = _by(db, "run")

    assert group["cost"]["metered"] == {"usd": None, "unpriced": ["mystery-1"]}


def test_a_price_in_config_wins_over_the_table(
    db: Database, tmp_path: Path
) -> None:
    with db.write() as conn:
        row = registry_store.get(conn, "models", "sonnet")
        config = {
            **json.loads(row["config"]),
            "price": {"input": 1000.0, "output": 0.0},
        }
        registry_store.replace(
            conn, "models", "sonnet", json.dumps(config), None, "t"
        )
    _, client = built(db, tmp_path, Reporting(Usage(10, 4, model="x")))

    [group] = _by(db, "run")

    # 10 input tokens a call at $1000 per million, nothing else charged
    assert group["cost"]["metered"]["usd"] == round(client.calls * 0.01, 6)


def test_a_subscription_call_is_an_estimate_never_spend(
    db: Database,
) -> None:
    run_id = enqueue(db, "brief", {}, started_by="ana")
    for provider in ("claude-code", "anthropic"):
        Ledgered(
            Reporting(),
            JobContext(db, job_id=run_id),
            role="brief",
            provider=provider,
        ).complete(
            CompletionRequest(
                model={"name": "m", "model": "x"}, system="", content=""
            )
        )

    [group] = _by(db, "run")

    one = round(SONNET.cost(10, 4, 2, 3), 6)
    assert group["cost"]["metered"]["usd"] == one
    assert group["cost"]["subscription_estimate"]["usd"] == one
    assert group["cost"]["billing"] == ["metered", "subscription"]


def test_a_tree_filter_reads_only_that_trees_runs(
    db: Database, tmp_path: Path
) -> None:
    built(db, tmp_path, Reporting())

    assert _by(db, "run", Filter(tree="default"))
    assert _by(db, "run", Filter(tree="elsewhere")) == []
    assert _by(db, "run", Filter(since="2999-01-01")) == []


def test_a_runs_totals_include_its_descendants(db: Database) -> None:
    root = enqueue(db, "noop", {}, started_by="ana")
    children = [enqueue(db, "noop", {}, parent_id=root) for _ in range(2)]
    grandchild = enqueue(db, "noop", {}, parent_id=children[0])
    for job_id in (*children, grandchild):
        Ledgered(
            Reporting(),
            JobContext(db, job_id=job_id),
            role="brief",
            provider="anthropic",
        ).complete(
            CompletionRequest(
                model={"name": "m", "model": "x"}, system="", content=""
            )
        )

    with db.connect() as conn:
        whole = for_jobs(conn, root)
        part = for_jobs(conn, children[0])
        none = for_jobs(conn, children[1] + "-missing")

    assert whole is not None and whole["calls"] == 3
    assert part is not None and part["calls"] == 2
    assert none is None


def test_the_longest_family_name_prices_a_dated_model() -> None:
    assert price_for("claude-opus-5-5-20260901") == PRICES["claude-opus-5-5"]
    assert price_for("claude-opus-5-20260101") == PRICES["claude-opus-5"]
    assert price_for("gpt-unknown") is None


def test_usage_is_served_to_a_reader_and_on_the_run(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, key)
    token = create_user(conn, "rita", "reader")[1]
    app = create_app(connection=conn, master_key=key, key_id=1)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as http:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        database = app.state.db
        run_id = enqueue(database, "noop", {}, started_by="ana")
        Ledgered(
            Reporting(),
            JobContext(database, job_id=run_id),
            role="brief",
            provider="anthropic",
        ).complete(
            CompletionRequest(
                model={"name": "m", "model": "x"}, system="", content=""
            )
        )
        rolled = http.get("/usage?by=user", headers=headers)
        refused = http.get("/usage?by=colour", headers=headers)
        run = http.get(f"/jobs/{run_id}", headers=headers).json()
    conn.close()

    assert rolled.status_code == 200
    assert [g["key"] for g in rolled.json()["groups"]] == ["ana"]
    assert refused.status_code == 400
    assert run["usage"]["calls"] == 1


def test_a_model_config_carries_its_own_price() -> None:
    base = {"name": "m", "kind": "text", "model": "x"}

    priced = Model.model_validate({**base, "price": {"input": 3, "output": 15}})

    assert priced.price is not None and priced.price.cache_read == 0.0
    with pytest.raises(ValidationError):
        Model.model_validate({**base, "price": {"input": -1, "output": 0}})


def test_a_paid_call_with_no_token_count_is_unknown_not_free(
    db: Database,
) -> None:
    # a remote embedding batch: billed per token, recorded with none (qa)
    run_id = enqueue(db, "embed", {}, started_by="ana")
    context = JobContext(db, job_id=run_id)
    config = {"name": "oai-embed", "model": "text-embedding-3-small"}
    metered(lambda texts: [[0.0]], context, config, provider="openai")(["a"])

    [group] = _by(db, "run")

    assert group["cost"]["metered"] == {
        "usd": None,
        "unpriced": ["text-embedding-3-small"],
    }


def test_a_refused_call_with_no_token_count_costs_nothing(
    db: Database,
) -> None:
    run_id = enqueue(db, "brief", {}, started_by="ana")
    with pytest.raises(LLMError):
        Ledgered(
            Refusing(),
            JobContext(db, job_id=run_id),
            role="brief",
            provider="anthropic",
        ).complete(
            CompletionRequest(
                model={"name": "m", "model": "x"}, system="", content=""
            )
        )

    [group] = _by(db, "run")

    assert group["failed"] == 1
    assert group["cost"]["metered"] == {"usd": 0.0, "unpriced": []}


class Refusing:
    def complete(self, request: CompletionRequest) -> CompletionResult:
        raise LLMError("upstream refused")
