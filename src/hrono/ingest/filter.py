"""Decide which files from a synced source cache are ingestable.

Pure classification over the synced tree: glob rules, then a size gate,
then a null-byte sniff for anything no glob caught — plus skipping ``.git``,
symlinks (which could escape the cache), and non-regular files. No file content
is read beyond the size stat and the sniff.

The glob rules are four layers, applied in this order, because ingesting a file
is not free — each one costs an embedding and a condense call immediately, while
its value to an agent reading the map is occasional:

- the caller's ``only`` is a true WHITELIST and is applied FIRST. Absent (the
  normal case) it decides nothing and the other three layers behave exactly as
  described below; present, a path matching none of its patterns is gone
  before ``exclude``, the baked list or ``include`` is even consulted. This is
  how a source is scoped to PART of a repository — a monorepo where only one
  package is wanted — which nothing else here can express, and whose absence
  cost a real run real money;
- the caller's ``exclude`` always wins over what survived ``only``;
- the baked ``DEFAULT_IGNORE`` groups EXTEND it rather than being replaced by
  it, so a source that excludes one directory of its own does not silently lose
  ``node_modules`` and lockfile protection;
- the caller re-admits what the baked groups caught, either with
  ``include_generated`` (the one group with a named opt-in — "I really do want
  that generated client") or file by file with an ``include`` pattern.

``replace_defaults: true`` drops the baked groups entirely — the escape hatch
for a caller who wants to own the list. The size, symlink and binary gates are
not patterns and are never dropped. A zero-byte file is skipped
here: it carries no content by definition, so admitting it only makes
every ``diff`` report it as new for ever.

CASE: the baked ignore list matches a LOWERCASED path; the caller's own
``only``, ``exclude`` and ``include`` match literally. That asymmetry is
deliberate. The baked list is a safety net and must be case-insensitive, or
``LOGO.SVG`` walks straight past the asset rule. The caller's
globs are their instructions, and every ordinary glob tool treats those
literally — making them case-insensitive would silently widen an ``exclude``
beyond what was written. Unifying breaks something in either direction, so the
behaviour is kept and written down instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hrono.ingest.split.constants import DEFAULT_IGNORE, OPTIONAL_IGNORE

_DEFAULT_MAX_SIZE_MB = 2.0
_SNIFF_BYTES = 8192


@dataclass(frozen=True)
class Seen:
    """One file of the cache, and why it is not ingested (None: it is)."""

    path: str
    size: int
    why: str | None


@dataclass(frozen=True)
class _Rules:
    """The resolved glob layers for one source's filter config."""

    only: tuple[str, ...]
    exclude: tuple[str, ...]
    ignore: tuple[tuple[str, str], ...]
    include: tuple[str, ...]

    def skips(self, rel: PurePosixPath) -> str | None:
        """Why ``rel`` is not worth a section under these rules, or None."""
        if self.only and not _matches(rel, self.only):
            return "outside filter.only"
        if _matches(rel, self.exclude):
            return "matched filter.exclude"
        lowered = PurePosixPath(rel.as_posix().lower())
        for group, pattern in self.ignore:
            if _matches(lowered, (pattern,)) and not _matches(
                rel, self.include
            ):
                return f"ignored by default: {group}"
        return None


def ingestable(
    cache: Path, filter_config: dict[str, object] | None
) -> tuple[str, ...]:
    """Return the sorted repo-relative paths eligible for splitting."""
    return tuple(
        seen.path for seen in survey(cache, filter_config) if seen.why is None
    )


def survey(
    cache: Path, filter_config: dict[str, object] | None
) -> tuple[Seen, ...]:
    """Every regular file of ``cache``, sorted, each with its verdict.

    The ONE place the filter decides: ``ingestable`` is this with the
    refused ones dropped, so a preview of what a source would ingest cannot
    drift from what ingest reads.
    """
    rules = _rules(filter_config)
    max_bytes = int(_max_size_mb(filter_config) * 1024 * 1024)

    seen: list[Seen] = []
    for path in cache.rglob("*"):
        rel = path.relative_to(cache)
        if ".git" in rel.parts or path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        why = rules.skips(PurePosixPath(rel.as_posix()))
        if why is None and size == 0:
            why = "empty"
        elif why is None and size > max_bytes:
            why = "over the size limit"
        elif why is None and _has_null_byte(path):
            why = "binary"
        seen.append(Seen(rel.as_posix(), size, why))
    return tuple(sorted(seen, key=lambda one: one.path))


def _rules(config: dict[str, object] | None) -> _Rules:
    return _Rules(
        only=_patterns(config, "only"),
        exclude=_patterns(config, "exclude"),
        ignore=_ignored(config),
        include=_patterns(config, "include"),
    )


def _ignored(
    config: dict[str, object] | None,
) -> tuple[tuple[str, str], ...]:
    if _flag(config, "replace_defaults"):
        return ()
    keep = _flag(config, "include_generated")
    return tuple(
        (group, pattern)
        for group, patterns in DEFAULT_IGNORE.items()
        if not (keep and group == OPTIONAL_IGNORE)
        for pattern in patterns
    )


def _patterns(config: dict[str, object] | None, key: str) -> tuple[str, ...]:
    value = config.get(key) if config else None
    if not isinstance(value, Iterable) or isinstance(value, str):
        return ()
    return tuple(str(pattern) for pattern in value)


def _flag(config: dict[str, object] | None, key: str) -> bool:
    return bool(config.get(key)) if config else False


def _matches(rel: PurePosixPath, patterns: tuple[str, ...]) -> bool:
    return any(rel.full_match(pattern) for pattern in patterns)


def _max_size_mb(config: dict[str, object] | None) -> float:
    if config and config.get("max_size_mb") is not None:
        return float(config["max_size_mb"])  # type: ignore[arg-type]
    return _DEFAULT_MAX_SIZE_MB


def _has_null_byte(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\x00" in handle.read(_SNIFF_BYTES)
