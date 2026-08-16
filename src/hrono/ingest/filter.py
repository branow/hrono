"""Decide which files from a synced source cache are ingestable.

Pure classification over the synced tree (#025): three gates in order — glob
exclude, size cap, then a null-byte sniff for anything no glob caught — plus
skipping ``.git``, symlinks (which could escape the cache), and non-regular
files. Defaults are baked from the spec and kept as data. No file content is
read beyond the size stat and the sniff.
"""

from __future__ import annotations

from pathlib import Path

_DEFAULT_EXCLUDE: tuple[str, ...] = ("**/node_modules/**", "**/*.lock")
_DEFAULT_MAX_SIZE_MB = 2.0
_SNIFF_BYTES = 8192


def ingestable(
    cache: Path, filter_config: dict[str, object] | None
) -> tuple[str, ...]:
    """Return the sorted repo-relative paths eligible for splitting."""
    exclude = _excludes(filter_config)
    max_bytes = int(_max_size_mb(filter_config) * 1024 * 1024)

    kept: list[str] = []
    for path in cache.rglob("*"):
        rel = path.relative_to(cache)
        if ".git" in rel.parts or path.is_symlink() or not path.is_file():
            continue
        if any(rel.full_match(pattern) for pattern in exclude):
            continue
        if path.stat().st_size > max_bytes:
            continue
        if _has_null_byte(path):
            continue
        kept.append(rel.as_posix())
    return tuple(sorted(kept))


def _excludes(config: dict[str, object] | None) -> tuple[str, ...]:
    if config and config.get("exclude") is not None:
        return tuple(str(p) for p in config["exclude"])  # type: ignore[union-attr]
    return _DEFAULT_EXCLUDE


def _max_size_mb(config: dict[str, object] | None) -> float:
    if config and config.get("max_size_mb") is not None:
        return float(config["max_size_mb"])  # type: ignore[arg-type]
    return _DEFAULT_MAX_SIZE_MB


def _has_null_byte(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\x00" in handle.read(_SNIFF_BYTES)
