"""A ledger group, worded for the page (#201, #202).

One reading of a roll-up for every page that shows spend — Home, a run, the
Usage page — so the three cannot word one run's cost three ways. Two kinds of
money stay apart: a metered provider's figure is spend, a subscription's is an
API-equivalent ESTIMATE and is never called spend nor added to it.
"""

from __future__ import annotations

from hrono.usage.present import duration, usd

UNKNOWN = "not recorded"


def describe(view: dict[str, object] | None) -> dict[str, object] | None:
    """Calls, tokens, model time and the two kinds of money, as text.

    ``None`` in, ``None`` out: whether that means "no calls" or "before the
    ledger" is the caller's to say, because only it knows the run's age.
    """
    if view is None:
        return None
    tokens = _map(view.get("tokens"))
    cost = _map(view.get("cost"))
    billing = cost.get("billing") or []
    cached = int(tokens.get("cache_read", 0)) + int(
        tokens.get("cache_creation", 0)
    )
    return {
        "calls": int(view["calls"]),  # type: ignore[call-overload]
        "failed": int(view["failed"]),  # type: ignore[call-overload]
        "tokens": f"{int(tokens.get('input', 0)):,} in, "
        f"{int(tokens.get('output', 0)):,} out",
        "volume": int(tokens.get("input", 0)) + int(tokens.get("output", 0)),
        "cached": f"{cached:,} cached" if cached else "",
        "time": duration(float(view["model_seconds"])),  # type: ignore[arg-type]
        "paid": usd(cost.get("metered"), "metered" in billing),
        "estimate": usd(
            cost.get("subscription_estimate"), "subscription" in billing
        ),
        "billed": "metered" in billing,
        "subscription": "subscription" in billing,
        "unpriced": _unpriced(cost),
        "upstream": ", ".join(map(str, view.get("upstream_models") or [])),
        "providers": ", ".join(map(str, view.get("providers") or [])),
    }


def _unpriced(cost: dict[str, object]) -> list[str]:
    return sorted(
        {
            str(name)
            for kind in ("metered", "subscription_estimate")
            for name in _map(cost.get(kind)).get("unpriced") or []  # type: ignore[attr-defined]
        }
    )


def _map(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
