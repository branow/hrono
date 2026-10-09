"""Roll the usage ledger up into the answers a person asks of it.

What did this run cost, which model is the expensive one, who started the runs
that cost the most, how many hours has a model been working. Every answer is a
GROUP of ledger rows with the same shape: calls, tokens by kind, model
time, and cost.

Cost keeps two kinds of money apart and never adds them. A provider billed per
token (``anthropic``, ``openai``) is METERED spend. ``claude-code`` bills
through the operator's subscription, so its tokens cost nothing per call; what
is reported for it is the API-equivalent figure, labelled an ESTIMATE. A call
whose model has no known price makes its total unknown — and the model is
named, so the operator can add the price — rather than quietly counting as
zero. A model loaded in process (``local``) costs nothing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field

from hrono.errors import BadRequest
from hrono.registry import store as registry_store
from hrono.usage.prices import Price, from_config, price_for

SUBSCRIPTION = frozenset({"claude-code"})
FREE = frozenset({"local"})

_KEYS: dict[str, str] = {
    "run": "c.run_id",
    "model": "c.model",
    "upstream-model": "c.upstream_model",
    "user": "c.started_by",
    "role": "c.role",
    "day": "substr(c.created_at, 1, 10)",
}
GROUPINGS = tuple(_KEYS)
LEDGER_MIGRATION = 36


@dataclass(frozen=True)
class Filter:
    """Which ledger rows a roll-up reads; every field narrows."""

    tree: str | None = None
    since: str | None = None
    until: str | None = None


EVERYTHING = Filter()


@dataclass
class _Money:
    usd: float = 0.0
    unpriced: set[str] = field(default_factory=set)

    def add(self, amount: float | None, name: str) -> None:
        if amount is None:
            self.unpriced.add(name)
            return
        self.usd += amount

    def view(self) -> dict[str, object]:
        return {
            "usd": None if self.unpriced else round(self.usd, 6),
            "unpriced": sorted(self.unpriced),
        }


@dataclass
class _Group:
    key: str | None
    calls: int = 0
    failed: int = 0
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    milliseconds: int = 0
    metered: _Money = field(default_factory=_Money)
    estimate: _Money = field(default_factory=_Money)
    billings: set[str] = field(default_factory=set)
    upstreams: set[str] = field(default_factory=set)
    providers: set[str] = field(default_factory=set)

    def spend(self) -> tuple[bool, float]:
        """Known money first, largest first; unknown cost sorts last."""
        if self.metered.unpriced or self.estimate.unpriced:
            return False, 0.0
        return True, self.metered.usd + self.estimate.usd

    def view(self) -> dict[str, object]:
        return {
            "key": self.key,
            "calls": self.calls,
            "failed": self.failed,
            "tokens": {
                "input": self.input,
                "output": self.output,
                "cache_read": self.cache_read,
                "cache_creation": self.cache_creation,
            },
            "model_seconds": round(self.milliseconds / 1000, 3),
            "upstream_models": sorted(self.upstreams),
            "providers": sorted(self.providers),
            "cost": {
                "metered": self.metered.view(),
                "subscription_estimate": self.estimate.view(),
                "billing": sorted(self.billings),
            },
        }


def usage(
    conn: sqlite3.Connection, by: str, where: Filter = EVERYTHING
) -> list[dict[str, object]]:
    """The ledger grouped ``by`` one of ``GROUPINGS``, costed at read time."""
    key = _KEYS.get(by)
    if key is None:
        raise BadRequest(
            f"unknown grouping: {by}", details={"allowed": list(GROUPINGS)}
        )
    clauses, params = _where(where)
    rows = conn.execute(
        f"SELECT {key} AS key, {_SUMS} FROM llm_calls c "  # noqa: S608
        f"LEFT JOIN jobs r ON r.id = c.run_id{clauses} "
        f"GROUP BY {key}, c.model, c.upstream_model, c.provider",
        params,
    ).fetchall()
    groups = _fold(conn, rows)
    ordered = (
        sorted(groups, key=lambda g: str(g.key))
        if by == "day"
        else sorted(groups, key=_Group.spend, reverse=True)
    )
    if by != "run":
        return [group.view() for group in ordered]
    return [{**group.view(), "run": _run(conn, group.key)} for group in ordered]


def total(
    conn: sqlite3.Connection, where: Filter = EVERYTHING
) -> dict[str, object] | None:
    """Every row the filter keeps as one group; None when there are none."""
    clauses, params = _where(where)
    rows = conn.execute(
        f"SELECT 'total' AS key, {_SUMS} FROM llm_calls c "  # noqa: S608
        f"LEFT JOIN jobs r ON r.id = c.run_id{clauses} "
        "GROUP BY c.model, c.upstream_model, c.provider",
        params,
    ).fetchall()
    groups = _fold(conn, rows)
    return groups[0].view() if groups else None


def for_jobs(conn: sqlite3.Connection, job_id: str) -> dict[str, object] | None:
    """One job's calls and every descendant's, as one group; None if none."""
    groups = _of_job(conn, job_id, "'job'")
    if not groups:
        return None
    groups[0].key = job_id
    return groups[0].view()


def for_job_by_role(
    conn: sqlite3.Connection, job_id: str
) -> list[dict[str, object]]:
    """The same calls as ``for_jobs``, one group per model role (the stage)."""
    return [group.view() for group in _of_job(conn, job_id, "c.role")]


def _of_job(conn: sqlite3.Connection, job_id: str, key: str) -> list[_Group]:
    rows = conn.execute(
        "WITH RECURSIVE down(id) AS (SELECT ? UNION ALL "
        "SELECT j.id FROM jobs j JOIN down ON j.parent_id = down.id) "
        f"SELECT {key} AS key, {_SUMS} FROM llm_calls c "  # noqa: S608
        "WHERE c.job_id IN (SELECT id FROM down) "
        f"GROUP BY {key}, c.model, c.upstream_model, c.provider",
        (job_id,),
    ).fetchall()
    return _fold(conn, rows)


def recorded_since(conn: sqlite3.Connection) -> str | None:
    """When this database began recording calls: its ledger migration's time.

    A job made before it has no rows because nothing was written then, which
    is not the same as a job that made no calls.
    """
    row = conn.execute(
        "SELECT applied_at FROM schema_migrations WHERE version = ?",
        (LEDGER_MIGRATION,),
    ).fetchone()
    return None if row is None else str(row["applied_at"])


_SUMS = (
    "c.model AS model, c.upstream_model AS upstream, c.provider AS provider, "
    "COUNT(*) AS calls, SUM(1 - c.ok) AS failed, "
    "SUM(c.ok = 1 AND c.input_tokens IS NULL AND c.output_tokens IS NULL) "
    "AS untold, "
    "COALESCE(SUM(c.input_tokens), 0) AS input, "
    "COALESCE(SUM(c.output_tokens), 0) AS output, "
    "COALESCE(SUM(c.cache_read_tokens), 0) AS cache_read, "
    "COALESCE(SUM(c.cache_creation_tokens), 0) AS cache_creation, "
    "SUM(c.duration_ms) AS milliseconds"
)


def _where(where: Filter) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if where.tree is not None:
        clauses.append("r.tree = ?")
        params.append(where.tree)
    if where.since is not None:
        clauses.append("c.created_at >= ?")
        params.append(where.since)
    if where.until is not None:
        clauses.append("c.created_at < ?")
        params.append(where.until)
    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def _fold(
    conn: sqlite3.Connection, rows: Iterable[sqlite3.Row]
) -> list[_Group]:
    overrides = _overrides(conn)
    groups: dict[str | None, _Group] = {}
    for row in rows:
        group = groups.setdefault(row["key"], _Group(row["key"]))
        group.calls += row["calls"]
        group.failed += row["failed"]
        group.input += row["input"]
        group.output += row["output"]
        group.cache_read += row["cache_read"]
        group.cache_creation += row["cache_creation"]
        group.milliseconds += row["milliseconds"]
        group.upstreams.add(str(row["upstream"] or row["model"]))
        group.providers.add(str(row["provider"]))
        _charge(group, row, overrides.get(row["model"]))
    return list(groups.values())


def _charge(group: _Group, row: sqlite3.Row, override: Price | None) -> None:
    provider = str(row["provider"])
    if provider in FREE:
        group.billings.add("local")
        return
    name = str(row["upstream"] or row["model"])
    amount = _amount(row, price_for(row["upstream"], override))
    if provider in SUBSCRIPTION:
        group.billings.add("subscription")
        group.estimate.add(amount, name)
        return
    group.billings.add("metered")
    group.metered.add(amount, name)


def _amount(row: sqlite3.Row, price: Price | None) -> float | None:
    """What these calls cost, or None when that cannot be known.

    A call that SUCCEEDED and recorded no tokens was paid for at a price
    nobody wrote down (an openai-compatible server that returns no usage),
    so its cost is unknown — not zero. A FAILED call with no tokens is
    counted as nothing: a refused request is not billed, and treating it as
    unknown would make every run that ever met an error unpriceable for good.
    """
    if row["untold"]:
        return None
    spent = row["input"] + row["output"] + row["cache_read"]
    if spent + row["cache_creation"] == 0:
        return 0.0
    if price is None:
        return None
    return price.cost(
        row["input"], row["output"], row["cache_read"], row["cache_creation"]
    )


def _overrides(conn: sqlite3.Connection) -> dict[str, Price]:
    """Each registered model's own price, by its configured name."""
    found: dict[str, Price] = {}
    for row in registry_store.list_all(conn, "models"):
        price = from_config(json.loads(row["config"]))
        if price is not None:
            found[str(row["name"])] = price
    return found


def _run(conn: sqlite3.Connection, run_id: str | None) -> dict[str, object]:
    """What a run WAS — its op, tree, starter and start — to show beside it."""
    row = conn.execute(
        "SELECT op, tree, started_by, created_at FROM jobs WHERE id = ?",
        (run_id,),
    ).fetchone()
    return {} if row is None else dict(row)
