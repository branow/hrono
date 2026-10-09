"""The runs list pages in SQL, and filters by the status rollup gives.

`store.page_roots` filters on a parent's DERIVED status, computed in SQL. That
is a second statement of `aggregate.rollup`'s rule, so every combination of
child statuses up to three children is held to rollup's answer here.
"""

from __future__ import annotations

import itertools
from pathlib import Path

from hrono.db.database import open_database
from hrono.jobs import store
from hrono.jobs.aggregate import PARTIAL, rollup
from hrono.jobs.model import JobStatus

STATUSES = tuple(str(status) for status in JobStatus)
COMBOS = [
    combo
    for size in range(4)
    for combo in itertools.combinations_with_replacement(STATUSES, size)
]


def test_the_sql_status_filter_agrees_with_rollup(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    for index, combo in enumerate(COMBOS):
        tree = f"t{index}"
        leaves = [(f"{tree}-{n}", "{}") for n in range(len(combo))]
        store.create_fanout(conn, tree, "sync", "{}", leaves, tree, "t")
        for (leaf, _scope), status in zip(leaves, combo, strict=True):
            store.set_status(conn, leaf, status, None, "t")

    answers = {
        combo: [
            status
            for status in (*STATUSES, PARTIAL)
            if store.count_roots(conn, f"t{index}", status=status)
        ]
        for index, combo in enumerate(COMBOS)
    }
    conn.close()

    expected = {
        combo: [
            rolled.status
            if (rolled := rollup(combo)) is not None
            else JobStatus.SUCCEEDED  # an empty fan-out is born succeeded
        ]
        for combo in COMBOS
    }
    assert answers == expected


def test_a_page_is_the_newest_runs_of_one_tree(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    for n in range(7):
        store.insert(conn, f"job_{n}", None, "a", "sync", "{}", f"t{n}")
    store.insert(conn, "job_child", "job_6", "a", "sync", "{}", "t9")
    store.insert(conn, "job_other", None, "b", "sync", "{}", "t9")
    store.insert(conn, "job_none", None, None, "monitor", "{}", "t9")

    page = store.page_roots(conn, "a", limit=3, offset=3)
    default = store.page_roots(conn, "default", limit=10, offset=0)
    counted = store.count_roots(conn, "a")
    conn.close()

    assert [row["id"] for row in page] == ["job_3", "job_2", "job_1"]
    assert [row["id"] for row in default] == ["job_none"]
    assert counted == 7


def test_a_second_status_widens_the_filter(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    store.create_fanout(
        conn, "mid", "sync", "{}", [("m1", "{}"), ("m2", "{}")], "t", "t"
    )
    store.set_status(conn, "m1", "succeeded", None, "t")
    store.create_fanout(conn, "busy", "sync", "{}", [("b1", "{}")], "t", "t")
    store.set_status(conn, "b1", "running", None, "t")

    def ids(**kept: str) -> set[str]:
        return {
            str(row["id"])
            for row in store.page_roots(conn, "t", limit=10, offset=0, **kept)
        }

    assert ids(status="running") == {"busy"}
    assert ids(status="running", also=PARTIAL) == {"busy", "mid"}
    assert store.count_roots(conn, "t", status="running", also=PARTIAL) == 2
    assert ids(also=PARTIAL) == {"busy", "mid"}
    assert ids() == {"busy", "mid"}
