"""Money and time as a person reads them: the CLI table and the panel."""

from __future__ import annotations

from hrono.server.i18n import gettext


def duration(seconds: float) -> str:
    """Model time in the unit a person reads it in."""
    if seconds < 60:
        return gettext("{value}s", value=f"{seconds:.1f}")
    if seconds < 3600:
        return gettext("{value}m", value=f"{seconds / 60:.1f}")
    return gettext("{value}h", value=f"{seconds / 3600:.2f}")


def usd(amount: object, billed: bool) -> str:
    """A money figure, "unknown" when unpriced, "-" when not billed so."""
    if not billed or not isinstance(amount, dict):
        return "-"
    known = amount.get("usd")
    if known is None:
        return "unknown"
    dollars = float(known)
    # a single call is a fraction of a cent; two places would show it as $0.00
    return f"${dollars:,.2f}" if dollars >= 1 else f"${dollars:.4f}"
