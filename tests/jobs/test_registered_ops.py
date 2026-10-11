"""Every op the tree and cluster stages promise is dispatchable by name."""

import hrono.cluster.levels  # noqa: F401
import hrono.cluster.monitor  # noqa: F401
import hrono.cluster.op  # noqa: F401
import hrono.cluster.repair  # noqa: F401
import hrono.ingest.sync  # noqa: F401
import hrono.tree.maintain  # noqa: F401
import hrono.tree.settle  # noqa: F401
import hrono.tree.sync_chain  # noqa: F401
import hrono.tree.update  # noqa: F401
from hrono.jobs.ops import OPS

EXPECTED = {
    "cluster",
    "cluster-briefs",
    "monitor",
    "repair",
    "maintain",
    "settle",
    "update",
    "sync-tree",
}


def test_the_stage_ops_are_registered() -> None:
    assert sorted(EXPECTED - set(OPS)) == []
    # `sync` is already the per-source ingest op, so the chain is `sync-tree`,
    # matching `build-tree`'s shape.
    assert OPS["sync"] is not OPS["sync-tree"]
