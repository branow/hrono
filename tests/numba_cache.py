"""Keep the clustering libraries' compiled kernels between test runs.

UMAP and pynndescent compile a few hundred numba kernels the first time a
process imports and runs them, about eight seconds of CPU, and only a handful
ask numba to keep the result on disk. Each umap worker of every run paid it
again. Defaulting ``cache=True`` lets numba store each kernel next to its
library's source and load it on the next run; numba checks the source file's
timestamp, so an upgraded library compiles afresh. The kernels are the same
code either way. A kernel numba cannot cache is simply compiled, as before.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


def install() -> None:
    """Make ``cache=True`` the default for every later ``numba.njit``."""
    try:
        import numba
    except ImportError:
        return
    if getattr(numba.njit, "_hrono_cached", False):
        return
    numba.njit = _cached(numba.njit)


def _cached(njit: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(njit)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("cache", True)
        return njit(*args, **kwargs)

    wrapper._hrono_cached = True  # type: ignore[attr-defined]
    return wrapper
