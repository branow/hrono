"""Build a test's git repository once per process, then copy it.

A helper that makes a small repository runs git four to six times, a few tens
of milliseconds each, and hundreds of tests call one. ``@memoized`` on such a
helper builds its repository once per process and set of arguments, into a
template of its own, and gives every later call a copy at the path it asked
for. A git repository records no path of its own, so the copy is the same
repository: the same files, history and commits. That last part is the only
difference a test could see: two repositories made with the same arguments in
one process now share their commit ids, where before they shared them only
when made in the same second.

The helper must make the repository from its arguments alone, at the path it
is given, and return that path, its ``str`` or its ``file://`` URI.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

_folder: Path | None = None


def memoized[Result](
    build: Callable[..., Result],
) -> Callable[..., Result]:
    made: dict[str, tuple[Path, Any]] = {}

    @functools.wraps(build)
    def make(path: Path, *args: Any, **kwargs: Any) -> Result:
        key = repr((args, sorted(kwargs.items())))
        if key not in made:
            template = Path(tempfile.mkdtemp(dir=_templates())) / path.name
            made[key] = (template, build(template, *args, **kwargs))
        template, result = made[key]
        shutil.copytree(template, path, symlinks=True)
        return _moved(result, template, path)

    return make


def _moved(result: Any, template: Path, path: Path) -> Any:
    if result == template:
        return path
    if result == str(template):
        return str(path)
    if result == template.as_uri():
        return path.as_uri()
    raise TypeError(f"a memoized repo helper returned {result!r}")


def _templates() -> Path:
    global _folder
    if _folder is None:
        _folder = Path(tempfile.mkdtemp(prefix="hrono-repos-"))
        atexit.register(shutil.rmtree, _folder, ignore_errors=True)
    return _folder
