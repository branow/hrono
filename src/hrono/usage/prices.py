"""What a token costs, per upstream model.

A baked table, USD per million tokens, matched on the LONGEST name prefix: a
provider reports a dated id (``claude-haiku-4-5-20251001``) and the price
belongs to the family. A registered model may carry its own ``price`` and that
wins over the table, so an operator who is billed differently — a negotiated
rate, a gateway, a model the table has never heard of — fixes it in config.

Cost is never stored. It is computed from the ledger's tokens when a roll-up is
read, so correcting a price here or in config corrects every run already
recorded.

Cache writes are priced at the 5-minute rate (1.25x input). The 1-hour rate is
2x, so a provider that writes the long cache — the ``claude-code`` CLI does —
costs somewhat more than this says; that provider is reported as an estimate
for exactly this kind of reason.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    """USD per million tokens of each kind."""

    input: float
    output: float
    cache_read: float
    cache_write: float

    def cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int,
        cache_write: int,
    ) -> float:
        return (
            input_tokens * self.input
            + output_tokens * self.output
            + cache_read * self.cache_read
            + cache_write * self.cache_write
        ) / 1_000_000


PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(10.0, 50.0, 0.25, 12.5),
    "claude-fable-5": Price(10.0, 50.0, 1.0, 12.5),
    "claude-opus-5-5": Price(4.0, 20.0, 0.2, 5.0),
    "claude-opus-5": Price(5.0, 25.0, 0.5, 6.25),
    "claude-opus-4-8": Price(5.0, 25.0, 0.5, 6.25),
    "claude-opus-4-7": Price(5.0, 25.0, 0.5, 6.25),
    "claude-opus-4-6": Price(5.0, 25.0, 0.5, 6.25),
    "claude-sonnet-5-5": Price(2.0, 10.0, 0.2, 2.5),
    "claude-sonnet-5": Price(2.0, 10.0, 0.2, 2.5),
    "claude-sonnet-4-6": Price(3.0, 15.0, 0.3, 3.75),
    "claude-sonnet-4-5": Price(3.0, 15.0, 0.3, 3.75),
    "claude-haiku-4-5": Price(1.0, 5.0, 0.1, 1.25),
}


def price_for(
    upstream: str | None, override: Price | None = None
) -> Price | None:
    """The price of ``upstream``: the override, else the table, else None."""
    if override is not None:
        return override
    if upstream is None:
        return None
    matches = [name for name in PRICES if upstream.startswith(name)]
    if not matches:
        return None
    return PRICES[max(matches, key=len)]


def from_config(config: object) -> Price | None:
    """A model config's own ``price`` block, when it has one."""
    if not isinstance(config, dict):
        return None
    price = config.get("price")
    if not isinstance(price, dict):
        return None
    return Price(
        input=float(price.get("input", 0.0)),
        output=float(price.get("output", 0.0)),
        cache_read=float(price.get("cache_read", 0.0)),
        cache_write=float(price.get("cache_write", 0.0)),
    )
