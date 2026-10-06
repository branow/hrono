"""The ``sync`` op (#137): bring an existing tree up to date, in order.

The incremental twin of ``maintain``. ``maintain`` builds a tree that does not
exist yet; this one refreshes a tree that does, touching only what changed —
which is hrono's whole differentiator, and until now was unreachable: every
stage below was implemented and tested while the only thing an operator could
trigger was a full cold rebuild.

    update -> propagate -> brief (stale leaves) -> brief-upper (every upper
           level, stale nodes only) -> monitor -> repair -> adopt (brief ->
           attach orphans at every level -> brief-upper again), always

PROPAGATE COMES BEFORE BRIEF, and the note that scoped this op had it the other
way round. ``propagate`` judges a leaf's NEW content against its STORED brief —
the old one — and marks the ancestors above it stale. Re-briefing the leaf first
rewrites that brief with the current member signature, so ``_changed_leaves``
finds nothing, nothing is judged, and no ancestor is ever marked: the upper
levels silently keep describing content that changed underneath them. The stage
order is the op's whole reason to exist and this is the sharpest example of it.

ONE VERB, because the order is load-bearing and the coupling is not obvious.
#122 was exactly the bug where the chain skipped a step: sections arrived
unsummarised, `brief` silently dropped them from its input, and the briefs cited
sources they had never read — a map that looks right and is quietly wrong, with
no error anywhere. Exposing the stages separately hands every operator the
chance to reproduce that. A single op cannot be sequenced incorrectly.

``settle`` is deliberately NOT in the chain (PO note D.3). It is expensive, and
hrono does not spend money unasked: the churn trigger INFORMS — the result says
whether it has fired — and an operator decides. Nothing here runs on a timer.

Like ``maintain``, this composes the existing ops rather than reimplementing
any stage, and a stage that raises fails the job with the stage named, leaving
the stages committed before it intact.
"""

from __future__ import annotations

from collections.abc import Mapping

from hrono.cluster.levels import attach_orphans
from hrono.cluster.monitor import monitor
from hrono.cluster.repair import repair
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.stages import Stages
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize.brief import brief
from hrono.summarize.brief_upper import brief_upper
from hrono.summarize.build_tree import build_tree
from hrono.summarize.propagate import propagate
from hrono.tree import changes
from hrono.tree.settle import should_settle
from hrono.tree.update import update


def sync(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
    client: object | None = None,
    core_labeler: object | None = None,
) -> Mapping[str, object]:
    """Run the incremental chain over ``tree``; report what each stage did.

    Each stage is timed and kept, and a failure names its stage (#213).
    """
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        before = changes.snapshot(conn, tree)
    run = Stages()
    ingested = run.run(
        "update",
        lambda: update(
            _stage(tree, "update"),
            context,
            encoder_for=encoder_for,
            client=client,
        ),
    )
    judged = run.run(
        "propagate",
        lambda: propagate(_stage(tree, "propagate"), context, client=client),
    )
    run.run(
        "brief", lambda: brief(_stage(tree, "brief"), context, client=client)
    )
    run.run(
        "brief-upper",
        lambda: _brief_upper_levels(tree, context, client=client),
    )
    measured = run.run(
        "monitor", lambda: monitor(_stage(tree, "monitor"), context)
    )
    repaired = run.run(
        "repair",
        lambda: repair(
            _stage(tree, "repair"), context, core_labeler=core_labeler
        ),
    )
    adopted = run.run(
        "adopt",
        lambda: _adopt(tree, context, encoder_for=encoder_for, client=client),
    )
    with context.database.connect() as conn:
        settle_due = should_settle(conn, tree)
        changed = changes.since(conn, tree, before)
    return run.outcome(
        {
            **_outcome(
                ingested,
                judged,
                measured,
                repaired,
                adopted=adopted,
                settle_due=settle_due,
            ),
            "tree": changed,
        }
    )


def _adopt(
    tree: str,
    context: JobContext,
    *,
    encoder_for: object | None,
    client: object | None,
) -> int:
    """Brief, attach and re-brief whatever this run left loose. ALWAYS.

    **This is why a tree could come out of a sync with two roots (#200).**
    A `repair` split retires a topic and makes two briefless leaves nothing
    parents; `update`'s drain emits leaves the same way. Both sat at level 0
    under nothing — on the map, two more tops beside the real root, and a root
    brief that silently stopped covering them.

    This used to run only "when repair changed anything", which was wrong
    twice over: the gate read ``repaired["pinned"]``, a count of pins HELD
    rather than work done, so any database with one pin ran it every sync —
    and a drain-emitted leaf on a run where repair really did nothing was
    never adopted at all, staying unreachable until the next settle or
    maintain. So it runs unconditionally: `brief` and `brief_upper` skip
    everything whose signature is fresh, and `attach_orphans` returns before
    its embed when a level has no orphans, so a steady tree pays three reads.
    """
    brief(_stage(tree, "brief"), context, client=client)
    attached = 0
    for level in _levels(context, tree, floor=0):
        attached += len(
            attach_orphans(
                _stage(tree, "cluster-briefs"),
                context,
                level=level,
                encoder_for=encoder_for,
            )
        )
    _brief_upper_levels(tree, context, client=client)
    if _forest(context, tree):
        # a drain on a one-topic tree leaves two tops and no level above to
        # attach to; only `build_tree` may mint the root that collects them,
        # and the export refuses a forest until something does.
        build_tree(
            _stage(tree, "build-tree"),
            context,
            client=client,
            encoder_for=encoder_for,
        )
    return attached


def _forest(context: JobContext, tree: str) -> bool:
    """More than one node at the tree's top level: no single root."""
    with context.database.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM nodes WHERE tree = ? AND level = "
            "(SELECT MAX(level) FROM nodes WHERE tree = ?)",
            (tree, tree),
        ).fetchone()
    return row is not None and int(row["n"]) > 1


def _brief_upper_levels(
    tree: str, context: JobContext, *, client: object | None
) -> None:
    """Run ``brief_upper`` at EVERY upper level, lowest first.

    The op briefs one level (scope ``level``, default 1), and the chain used to
    call it bare — so a stale brief at level 2 or above, including the root's,
    was marked by ``propagate`` and then never rewritten by any sync; only a
    full ``maintain`` passed explicit levels. Lowest first, because a level's
    brief is written over its CHILDREN's briefs, so level N must be current
    before level N+1 reads it.
    """
    for level in _levels(context, tree, floor=1):
        brief_upper(
            _stage(tree, "brief-upper", level=level), context, client=client
        )


def _levels(context: JobContext, tree: str, *, floor: int) -> tuple[int, ...]:
    """The tree's distinct levels at or above ``floor``, ascending."""
    with context.database.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT level FROM nodes WHERE tree = ? AND level >= ? "
            "ORDER BY level",
            (tree, floor),
        ).fetchall()
    return tuple(int(row["level"]) for row in rows)


def _outcome(
    ingested: Mapping[str, object],
    judged: Mapping[str, object],
    measured: Mapping[str, object],
    repaired: Mapping[str, object],
    *,
    adopted: int,
    settle_due: bool,
) -> Mapping[str, object]:
    """What the run did, for the operator (#132).

    One verb over six stages is a black box unless it says what happened, which
    is the honest objection to this design and the thing that answers it.
    ``settle_due`` is the trigger INFORMING: hrono has not run it and will not.
    Every stage that makes a judgement contributes its counts (#133) — a
    force-assign, a freed pioneer, a collected build — because those are the
    decisions an operator would act on and they used to be visible nowhere.
    """
    return {
        "changed": ingested.get("changed", False),
        "forced": ingested.get("forced", 0),
        "parked": ingested.get("parked", 0),
        "judged": judged.get("judged", 0),
        "propagated": judged.get("propagated", 0),
        "skipped": judged.get("skipped", 0),
        "abstained": judged.get("abstained", 0),
        "misfit_rate": measured.get("rate"),
        "above_baseline": measured.get("above_baseline", False),
        "repaired": dict(repaired),
        "adopted": adopted,
        "settle_due": settle_due,
        "incomplete": bool(judged.get("incomplete", False)),
    }


def _stage(tree: str, op: str, *, level: int | None = None) -> Job:
    return Job(
        id=f"sync-{op}",
        parent_id=None,
        tree=tree,
        op=op,
        scope={} if level is None else {"level": level},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


OPS["sync-tree"] = sync
