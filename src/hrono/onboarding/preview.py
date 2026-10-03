"""What a source's filter keeps, from the files and nothing else (#219).

No model is called and nothing is stored: the answer is `ingest.filter.survey`
read over the fetched cache. That is the same function ingest reads its files
through, so the preview is not a second statement of the filter that could
drift from it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from hrono.ingest.filter import Seen, survey

LARGEST = 5


@dataclass(frozen=True)
class Refusal:
    """Files left out for one reason."""

    why: str
    files: int
    bytes: int


@dataclass(frozen=True)
class Preview:
    kept: tuple[Seen, ...]
    largest: tuple[Seen, ...]
    refused: tuple[Refusal, ...]

    @property
    def files(self) -> int:
        return len(self.kept)

    @property
    def bytes(self) -> int:
        return sum(one.size for one in self.kept)


def preview(cache: Path, filter_config: dict[str, object] | None) -> Preview:
    """Sort ``cache`` into what is read and what is not, and why."""
    seen = survey(cache, filter_config)
    kept = tuple(one for one in seen if one.why is None)
    refused: dict[str, list[int]] = defaultdict(list)
    for one in seen:
        if one.why is not None:
            refused[one.why].append(one.size)
    return Preview(
        kept=kept,
        largest=tuple(sorted(kept, key=lambda one: -one.size)[:LARGEST]),
        refused=tuple(
            Refusal(why, len(sizes), sum(sizes))
            for why, sizes in sorted(
                refused.items(), key=lambda item: -sum(item[1])
            )
        ),
    )
