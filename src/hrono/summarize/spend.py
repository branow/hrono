"""What an op spent, in tokens (#179).

The spec's job shape has carried a ``cost`` field since M0 and nothing filled
it. Tokens live in the op's OUTCOME rather than a new column, because `result`
is already defined as "a JSON object of COUNTS, never prose" (0027) and a token
count is exactly that — so `GET /jobs/<id>` derives `cost` at read time the way
#172 derives a parent's status, with no second place for it to go stale.

Only tokens. Converting them to money needs a price per model, which is config
this project does not have and which goes stale the moment a provider changes
it — and a made-up number shown to someone deciding whether to spend is worse
than no number.
"""

from __future__ import annotations

from collections.abc import Sequence

Usage = tuple[int, int]  # (input tokens, output tokens) of one completion


def counts(spent: Sequence[Usage]) -> dict[str, int] | None:
    """Sum a run's completions, or None when it made none.

    None and not a zero: an op that calls no model has no cost to report, and
    `{"input": 0, "output": 0}` on a `cluster` job invites the reader to wonder
    which model it used.
    """
    if not spent:
        return None
    return {
        "input": sum(usage[0] for usage in spent),
        "output": sum(usage[1] for usage in spent),
    }
