"""``hrono usage``: what the model calls cost, as a table (#202).

The same roll-ups as ``GET /usage``, printed for a person: one row per group,
tokens by kind, model time, and the two kinds of money in separate
columns — metered spend, and the API-equivalent estimate for calls a
subscription paid for. Neither is ever added to the other.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

import typer

from hrono.client.http import from_profile
from hrono.usage.present import duration, usd

_COLUMNS = (
    ("CALLS", 6),
    ("FAILED", 6),
    ("INPUT", 10),
    ("OUTPUT", 10),
    ("CACHE-READ", 11),
    ("CACHE-WRITE", 11),
    ("MODEL-TIME", 10),
    ("METERED", 10),
    ("SUBSCRIPTION*", 13),
)


def usage(
    by: Annotated[
        str, typer.Option(help="run, model, upstream-model, user or day")
    ] = "model",
    tree: Annotated[str | None, typer.Option(help="Only this tree.")] = None,
    since: Annotated[
        str | None, typer.Option(help="From this date (YYYY-MM-DD) on.")
    ] = None,
) -> None:
    """Show tokens, model time and cost, grouped by run, model, user or day."""
    query = {
        key: value
        for key, value in (("by", by), ("tree", tree), ("since", since))
        if value
    }
    answer = from_profile().get(f"/usage?{urlencode(query)}")
    groups = answer.get("groups") if isinstance(answer, dict) else None
    if not groups:
        typer.echo("no model calls recorded")
        return
    for line in render(by, groups):
        typer.echo(line)


def render(by: str, groups: list[dict[str, object]]) -> list[str]:
    """The table, its header, and what a reader needs to trust the money."""
    labels = [_label(by, group) for group in groups]
    width = max(len(by.upper()), *(len(label) for label in labels))
    header = by.upper().ljust(width) + "".join(
        name.rjust(size + 1) for name, size in _COLUMNS
    )
    rows = [
        label.ljust(width)
        + "".join(
            cell.rjust(size + 1)
            for cell, (_, size) in zip(_cells(group), _COLUMNS, strict=True)
        )
        for label, group in zip(labels, groups, strict=True)
    ]
    notes = [
        "",
        "* calls billed by subscription (claude-code): the API-equivalent "
        "price, an estimate, not money spent.",
    ]
    unpriced = sorted({name for group in groups for name in _unpriced(group)})
    if unpriced:
        notes.append(
            "unknown: no price for "
            + ", ".join(unpriced)
            + " — add a `price` to that model's config."
        )
    return [header, *rows, *notes]


def _label(by: str, group: dict[str, object]) -> str:
    key = str(group.get("key") or "(unknown)")
    run = group.get("run")
    if by != "run" or not isinstance(run, dict) or not run:
        return key
    return f"{key} {run.get('op')} by {run.get('started_by') or '(unknown)'}"


def _cells(group: dict[str, object]) -> list[str]:
    tokens = group.get("tokens")
    counts = tokens if isinstance(tokens, dict) else {}
    cost = group.get("cost")
    money = cost if isinstance(cost, dict) else {}
    billing = money.get("billing") or []
    return [
        f"{group.get('calls', 0):,}",
        f"{group.get('failed', 0):,}",
        f"{counts.get('input', 0):,}",
        f"{counts.get('output', 0):,}",
        f"{counts.get('cache_read', 0):,}",
        f"{counts.get('cache_creation', 0):,}",
        duration(float(group.get("model_seconds") or 0)),  # type: ignore[arg-type]
        usd(money.get("metered"), "metered" in billing),
        usd(money.get("subscription_estimate"), "subscription" in billing),
    ]


def _unpriced(group: dict[str, object]) -> list[str]:
    cost = group.get("cost")
    money = cost if isinstance(cost, dict) else {}
    return [
        str(name)
        for kind in ("metered", "subscription_estimate")
        if isinstance(money.get(kind), dict)
        for name in money[kind].get("unpriced") or []
    ]
