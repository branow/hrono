"""Suite-wide pytest setup.

The clustering tests run the real UMAP -> HDBSCAN recipe. Under
``pytest -n auto`` every worker would start numba and BLAS thread pools
sized to the whole machine, and the workers fight over the cores: the same
test took twice as long as it does alone. One thread per worker keeps the
parallelism where xdist put it. The variables are read when numpy and numba
load, so they are set here, before any test module imports them.
"""

from __future__ import annotations

import os

import pytest

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMBA_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

# Imported after the variables above, which numpy and numba read on load.
from tests import numba_cache, template_db  # noqa: E402

# Before any test module imports ``open_database``: a new database is a copy
# of one migrated once per process (see tests/template_db.py).
template_db.install()
# Before umap loads: its compiled kernels are kept on disk between runs (see
# tests/numba_cache.py), so a warm run skips most of the cost described below.
numba_cache.install()


# Importing umap and compiling its numba kernels costs about nine seconds once
# per process, and it lands in whichever test first runs a real build. Spread
# over eight workers that is eight times nine seconds of CPU, all at once.
# ``--dist loadgroup`` sends every module below to one of two workers, so the
# cost is paid twice, not eight times, and the rest of those tests run warm.
# A new module that runs the real UMAP -> HDBSCAN recipe belongs in this set.
_UMAP_MODULES = frozenset(
    {
        "tests/cluster/test_build.py",
        "tests/cluster/test_incubator.py",
        "tests/cluster/test_known_groups.py",
        "tests/cluster/test_levels.py",
        "tests/cluster/test_op.py",
        "tests/cluster/test_warm_stability.py",
        "tests/server/test_manual_split.py",
        "tests/server/test_ui_surgery.py",
        "tests/tree/test_settle.py",
        "tests/tree/test_update.py",
    }
)


# Each worker that runs a browser test launches Chromium and a live server
# for the module, a second or two each. Left to xdist, all eight workers did.
# Two groups pay it twice and still split the module's work in half.
_BROWSER_MODULE = "tests/server/test_ui_browser.py"


# A module that builds its world once (tests/world.py) builds it again on every
# worker that draws one of its tests. These run on one worker each; the find
# page borrows the ask page's world, so they share one.
_WORLD_GROUPS = {
    "tests/server/test_ui_ask.py": "ask-world",
    "tests/server/test_ui_find.py": "ask-world",
    "tests/tree/test_sync_chain.py": "sync-chain-world",
}


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    browsers = 0
    for item in items:
        module = item.nodeid.split("::")[0]
        if module == _BROWSER_MODULE:
            group = f"browser-{browsers % 2}"
            item.add_marker(pytest.mark.xdist_group(group))
            browsers += 1
        elif module in _WORLD_GROUPS:
            item.add_marker(pytest.mark.xdist_group(_WORLD_GROUPS[module]))
        elif module in _UMAP_MODULES:
            # Two groups, not one: the tree tests alone are about half the
            # warm work, and one worker holding all of it is the whole run.
            group = "umap-tree" if module.startswith("tests/tree/") else "umap"
            item.add_marker(pytest.mark.xdist_group(group))
