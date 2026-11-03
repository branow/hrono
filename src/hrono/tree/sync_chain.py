"""The ``sync`` op: bring an existing tree up to date, in order.

The incremental twin of ``maintain``. ``maintain`` builds a tree that does not
exist yet; this one refreshes a tree that does, touching only what changed —
which is hrono's whole differentiator. Without it every stage below is
implemented and tested while the only thing an operator can trigger is a full
cold rebuild.

    update -> propagate -> brief (stale leaves) -> brief-upper (every upper
           level, stale nodes only) -> monitor -> repair -> adopt (brief ->
           attach orphans at every level -> brief-upper again), always ->
           embed (the briefs just written, so recall sees them)

PROPAGATE COMES BEFORE BRIEF, not the other way round. ``propagate`` judges a
leaf's NEW content against its STORED brief — the old one — and marks the
ancestors above it stale. Re-briefing the leaf first rewrites that brief with
the current member signature, so ``_changed_leaves`` finds nothing, nothing is
judged, and no ancestor is ever marked: the upper levels silently keep
describing content that changed underneath them. The stage order is the op's
whole reason to exist and this is the sharpest example of it.

ONE VERB, because the order is load-bearing and the coupling is not obvious. A
chain that skips a step lets sections arrive unsummarised: `brief` silently
drops them from its input, and the briefs cite sources they have never read — a
map that looks right and is quietly wrong, with no error anywhere. Exposing the
stages separately hands every operator the chance to reproduce that. A single op
cannot be sequenced incorrectly.

``settle`` is deliberately NOT in the chain. It is expensive, and
hrono does not spend money unasked: the churn trigger INFORMS — the result says
whether it has fired — and an operator decides. Nothing here runs on a timer.

Like ``maintain``, this composes the existing ops rather than reimplementing
any stage, and a stage that raises fails the job with the stage named, leaving
the stages committed before it intact.
"""

from __future__ import annotations

from collections.abc import Mapping

from hrono.cluster.levels import attach_orphans
from hrono.cluster.monitor import drop_baseline, monitor
from hrono.cluster.repair import repair
from hrono.embed.op import embed
from hrono.health import report
from hrono.health.upgrade import moving_sections
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.stages import Stages, recorder
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize import review
from hrono.summarize.brief import brief
from hrono.summarize.brief_upper import brief_upper
from hrono.summarize.build_tree import build_tree, total_insights
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

    Each stage is timed and kept, and a failure names its stage.
    """
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        before = changes.snapshot(conn, tree)

    def embedded() -> Mapping[str, object]:
        return embed(_stage(tree, "embed"), context, encoder_for=encoder_for)

    def repair_stage() -> Mapping[str, object]:
        return repair(
            _stage(tree, "repair"), context, core_labeler=core_labeler
        )

    def adopt() -> tuple[int, dict[str, object]]:
        return _adopt(tree, context, encoder_for=encoder_for, client=client)

    run = Stages(report=recorder(context.database, job.id))
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
    reviewed = [
        run.run(
            "brief-upper",
            lambda: _brief_upper_levels(tree, context, client=client),
        )
    ]
    # the monitor and repair below read vectors: of the condensations a tree
    # built before they were embedded still lacks, and of the briefs just
    # written. Embedded here, they work in the space the tree will be in, not
    # one the last stage replaces, and an unchanged source finds nothing to move
    with context.database.connect() as conn:
        respaced = moving_sections(conn, tree) > 0
    run.run("embed", embedded)
    if respaced:
        # a baseline measured on the raw vectors compares nothing to the
        # condensation vectors the tree is now placed by: measure it afresh
        with context.database.write() as conn:
            drop_baseline(conn, tree)
    measured = run.run(
        "monitor", lambda: monitor(_stage(tree, "monitor"), context)
    )
    repaired = run.run("repair", repair_stage)
    reshaped = bool(repaired["split"] or repaired["dissolved"])
    adopted, late = run.run("adopt", adopt)
    reviewed.append(late)
    # brief, brief-upper and adopt wrote node:// brief passages; vectorise
    # them, as maintain does, or recall's cosine leg never sees a brief
    # written by a sync (the v9 eval tree had 11,000 of 11,006 unembedded)
    run.run("embed", embedded)
    if reshaped:
        # the topics a split or dissolve made had no brief, so no vector, when
        # repair placed them: place once more now they do, or the next sync
        # moves them and rewrites the briefs above for an unchanged source
        again = run.run("repair", repair_stage)
        repaired = {
            key: _total(value, again.get(key)) if key != "pinned" else value
            for key, value in repaired.items()
        }
        if again["migrated"] or again["reparented"]:
            adopted_more, late = run.run("adopt", adopt)
            adopted += adopted_more
            reviewed.append(late)
            run.run("embed", embedded)
    run.run("health", lambda: report.refresh(context.database, tree))
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
            **_insights(reviewed),
            "tree": changed,
        }
    )


def _adopt(
    tree: str,
    context: JobContext,
    *,
    encoder_for: object | None,
    client: object | None,
) -> tuple[int, dict[str, object]]:
    """Brief, attach and re-brief whatever this run left loose. ALWAYS.

    **This is why a tree could come out of a sync with two roots.**
    A `repair` split retires a topic and makes two briefless leaves nothing
    parents; `update`'s drain emits leaves the same way. Both sat at level 0
    under nothing — on the map, two more tops beside the real root, and a root
    brief that silently stopped covering them.

    It must not be gated on "repair changed anything": a drain-emitted leaf on
    a run where repair really did nothing would never be adopted, staying
    unreachable until the next settle or maintain (and ``repaired["pinned"]``
    counts pins HELD, not work done, so it is no such gate). So it runs
    unconditionally: `brief` and `brief_upper` skip
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
    reviewed = [_brief_upper_levels(tree, context, client=client)]
    if _forest(context, tree):
        # a drain on a one-topic tree leaves two tops and no level above to
        # attach to; only `build_tree` may mint the root that collects them,
        # and the export refuses a forest until something does.
        build_tree(
            _stage(tree, "build-tree"),
            context,
            client=client,
            encoder_for=encoder_for,
            # the passes below are the sync's own: a topic below its
            # threshold gets none, which the build's root rule would not say
            reviewing=False,
        )
        reviewed.append(_brief_upper_levels(tree, context, client=client))
    return attached, _sum(reviewed)


def _forest(context: JobContext, tree: str) -> bool:
    """More than one node at the tree's top level: no single root."""
    with context.database.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM nodes WHERE tree = ? AND level = "
            "(SELECT MAX(level) FROM nodes WHERE tree = ?)",
            (tree, tree),
        ).fetchone()
    return row is not None and int(row["n"]) > 1


def _total(first: object, second: object) -> object:
    return int(first) + int(second or 0)  # type: ignore[call-overload]


def _sum(runs: list[dict[str, object]]) -> dict[str, object]:
    """The insights outcomes of the runs in one stage, added up (or none)."""
    ran = [one for one in runs if one]
    return total_insights(ran) if ran else {}


def _insights(runs: list[dict[str, object]]) -> dict[str, object]:
    """The ``insights`` key of the sync's outcome, when a pass was looked at."""
    total = _sum(runs)
    return {"insights": total} if total else {}


def _brief_upper_levels(
    tree: str, context: JobContext, *, client: object | None
) -> dict[str, object]:
    """Run ``brief_upper`` at EVERY upper level, lowest first.

    The op briefs one level (scope ``level``, default 1), so calling it bare
    leaves a stale brief at level 2 or above, including the root's, marked by
    ``propagate`` and then never rewritten by any sync. Lowest first, because a
    level's brief is written over its CHILDREN's briefs, so level N must be
    current before level N+1 reads it.

    With the tree's insights on, a level's passes run right after its briefs,
    before the level above is written: a stale brief that had a pass was just
    rewritten by the cheaper model and is reviewed again, a topic whose count
    first reaches the threshold gets its first pass, and the parent is briefed
    from the extended brief. The counter decides, so a topic under the
    threshold gets none and a sync that changed nothing calls no model.
    """
    runs: list[dict[str, object]] = []
    for level in _levels(context, tree, floor=1):
        brief_upper(
            _stage(tree, "brief-upper", level=level), context, client=client
        )
        runs.append(
            review.run(
                context,
                tree,
                levels=[level],
                root=False,
                client=client,  # type: ignore[arg-type]
                rebrief=lambda at: brief_upper(
                    _stage(tree, "brief-upper", level=at),
                    context,
                    client=client,  # type: ignore[arg-type]
                ),
            )
        )
    return _sum(runs)


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
    """What the run did, for the operator.

    One verb over six stages is a black box unless it says what happened, which
    is the honest objection to this design and the thing that answers it.
    ``settle_due`` is the trigger INFORMING: hrono has not run it and will not.
    Every stage that makes a judgement contributes its counts — a
    force-assign, a freed pioneer, a collected build — because those are the
    decisions an operator would act on and nothing else makes them visible.
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
