"""What a first build would cost, said before it starts.

An ESTIMATE, and it says what it rests on. The only thing known exactly is how
many sections the files cut into — counted by the same cut a split stores
(`split_op.sections_of`). Everything else is a per-call size and time that was
MEASURED on real builds and is baked below: no install has a history to
project from before its first build, and an invented number shown to someone
deciding whether to spend is worse than none.

Money is the usage price table applied to those tokens, and keeps its two
kinds apart: a metered provider's figure is what the build would be billed, a
subscription's is the API-equivalent estimate and is never called spend.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from hrono.ingest.filter import ingestable
from hrono.ingest.split import structure
from hrono.ingest.split_op import sections_of
from hrono.registry import store
from hrono.summarize.resolve import resolve_prompt, resolve_text_model
from hrono.usage.prices import from_config, price_for
from hrono.usage.rollup import SUBSCRIPTION

# Measured on a real build of a 52-section repository through claude-code:
# 3 leaf topics and one root, 226 s. Bytes of code or prose per token.
BYTES_PER_TOKEN = 3.5
# Tokens the model WRITES per call, by how the provider is reached. Through the
# CLI the count includes work the answer does not show (a 760-character
# condensation was billed as 866 tokens); a metered API bills what is written,
# which is the text's own length at BYTES_PER_TOKEN.
WRITTEN = {
    "claude-code": {"condense": 866, "brief": 2480, "brief-upper": 2680},
    "api": {"condense": 220, "brief": 1670, "brief-upper": 1670},
}
# What a condensation and a brief read as when a brief is written from them.
TEXT = {"condense": 220, "brief": 1670}
# How many sections a leaf topic holds, and how many topics an upper one.
SECTIONS_PER_TOPIC = 15
UPPER_FANOUT = 8
# A claude-code call carries a fixed harness prompt, billed as cache:
# read at the cache rate, plus the part written fresh.
HARNESS_READ = 11000
HARNESS_WRITE = 3000
# Seconds one call takes. Measured through the CLI; for the API, derived from
# what it writes (a second and a half, then 80 tokens a second) and not yet
# measured.
CLI_SECONDS = {"condense": 9.4, "brief": 17.0, "brief-upper": 17.5}
API_LATENCY = 1.5
API_TOKENS_PER_SECOND = 80
# Fetching, splitting, embedding and grouping, which call no model.
FIXED_SECONDS = 40
SECONDS_PER_SECTION = 0.5

ROLES = ("condense", "brief", "brief-upper")


@dataclass(frozen=True)
class Stage:
    role: str
    model: str
    upstream: str
    provider: str
    calls: int
    input: int
    output: int
    seconds: float
    usd: float | None

    @property
    def subscription(self) -> bool:
        return self.provider in SUBSCRIPTION


@dataclass(frozen=True)
class Cut:
    """What a set of sources' files cut into."""

    files: int
    sections: int
    bytes: int


@dataclass(frozen=True)
class Estimate:
    cut: Cut
    stages: tuple[Stage, ...]
    basis: str

    @property
    def sections(self) -> int:
        return self.cut.sections

    @property
    def calls(self) -> int:
        return sum(stage.calls for stage in self.stages)

    @property
    def input(self) -> int:
        return sum(stage.input for stage in self.stages)

    @property
    def output(self) -> int:
        return sum(stage.output for stage in self.stages)

    @property
    def seconds(self) -> float:
        """Model time plus the work that calls no model."""
        return (
            sum(stage.seconds for stage in self.stages)
            + FIXED_SECONDS
            + SECONDS_PER_SECTION * self.cut.sections
        )

    @property
    def metered(self) -> float | None:
        """What a metered provider would bill; None when a price is unknown."""
        return _money([s for s in self.stages if not s.subscription])

    @property
    def subscription(self) -> float | None:
        """The API-equivalent of the subscription's calls; never spend."""
        return _money([s for s in self.stages if s.subscription])

    @property
    def billed(self) -> bool:
        return any(not s.subscription for s in self.stages)

    @property
    def subscribed(self) -> bool:
        return any(s.subscription for s in self.stages)

    @property
    def unpriced(self) -> tuple[str, ...]:
        return tuple(sorted({s.upstream for s in self.stages if s.usd is None}))


def cut(caches: list[tuple[Path, dict[str, object] | None]]) -> Cut:
    """Count the sections the ingestable files of each cache are cut into."""
    files = sections = size = 0
    for cache, filter_config in caches:
        for path in ingestable(cache, filter_config):
            raw = (cache / path).read_bytes()
            made = sections_of(structure(Path(path), raw), path, raw)
            files += 1
            sections += len(made)
            size += len(raw)
    return Cut(files, sections, size)


def estimate(conn: sqlite3.Connection, found: Cut, width: int) -> Estimate:
    """The calls, tokens, time and money of building ``found`` from nothing."""
    plan = _plan(found)
    return Estimate(
        cut=found,
        stages=tuple(_stage(conn, role, plan[role], width) for role in ROLES),
        basis=(
            f"{found.sections} sections counted from {found.files} files; "
            f"calls and tokens sized from a measured build of a similar "
            f"repository (about {SECTIONS_PER_TOPIC} sections per topic); "
            f"the number of topics, and so of briefs, is the loosest part"
        ),
    )


def _plan(found: Cut) -> dict[str, tuple[int, int]]:
    """Per role: (calls, content tokens in per call)."""
    sections = max(found.sections, 1)
    leaves = max(1, round(sections / SECTIONS_PER_TOPIC))
    upper, level = 0, leaves
    while level > 1:
        level = math.ceil(level / UPPER_FANOUT)
        upper += level
    section_tokens = round(found.bytes / sections / BYTES_PER_TOKEN)
    return {
        "condense": (found.sections, section_tokens),
        "brief": (leaves, round(sections / leaves * TEXT["condense"])),
        "brief-upper": (upper, UPPER_FANOUT * TEXT["brief"]),
    }


def _stage(
    conn: sqlite3.Connection,
    role: str,
    plan: tuple[int, int],
    width: int,
) -> Stage:
    calls, content = plan
    model = resolve_text_model(conn, {}, role)
    _, template = resolve_prompt(conn, role)
    provider = _provider(conn, model)
    cli = provider in SUBSCRIPTION
    out = WRITTEN["claude-code" if cli else "api"][role]
    prompt = round(len(template) / BYTES_PER_TOKEN) + content
    price = price_for(_upstream(conn, model), from_config(model))
    cached = (HARNESS_READ, HARNESS_WRITE + prompt) if cli else (0, 0)
    usd = (
        None
        if price is None
        else price.cost(
            0 if cli else prompt * calls,
            out * calls,
            cached[0] * calls,
            cached[1] * calls,
        )
    )
    each = (
        CLI_SECONDS[role] if cli else API_LATENCY + out / API_TOKENS_PER_SECOND
    )
    return Stage(
        role=role,
        model=str(model["name"]),
        upstream=str(model["model"]),
        provider=provider,
        calls=calls,
        input=(prompt + HARNESS_READ + HARNESS_WRITE if cli else prompt)
        * calls,
        output=out * calls,
        seconds=math.ceil(calls / max(width, 1)) * each,
        usd=usd,
    )


def _upstream(conn: sqlite3.Connection, model: dict[str, object]) -> str:
    """The id the provider says it ran, when a call has said it.

    A model may be registered under an alias (`haiku`) the price table does not
    know. Registering it called it once, and the ledger kept the id the
    provider answered with, so that is what is priced.
    """
    row = conn.execute(
        "SELECT upstream_model FROM llm_calls WHERE model = ? "
        "AND upstream_model IS NOT NULL ORDER BY id DESC LIMIT 1",
        (str(model["name"]),),
    ).fetchone()
    return str(model["model"]) if row is None else str(row["upstream_model"])


def _provider(conn: sqlite3.Connection, model: dict[str, object]) -> str:
    row = store.get(conn, "connections", str(model.get("connection")))
    return "" if row is None else str(json.loads(row["config"])["provider"])


def _money(stages: list[Stage]) -> float | None:
    if any(s.usd is None for s in stages):
        return None
    return round(sum(s.usd or 0.0 for s in stages), 4)
