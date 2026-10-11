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

from tests import template_db

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMBA_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

# Before any test module imports ``open_database``: a new database is a copy
# of one migrated once per process (see tests/template_db.py).
template_db.install()


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


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        module = item.nodeid.split("::")[0]
        if module in _UMAP_MODULES:
            # Two groups, not one: the tree tests alone are about half the
            # warm work, and one worker holding all of it is the whole run.
            group = "umap-tree" if module.startswith("tests/tree/") else "umap"
            item.add_marker(pytest.mark.xdist_group(group))
