"""The ``sync`` op (#137): bring an existing tree up to date, in order.

The incremental twin of ``maintain``. ``maintain`` builds a tree that does not
exist yet; this one refreshes a tree that does, touching only what changed —
which is hrono's whole differentiator, and until now was unreachable: every
stage below was implemented and tested while the only thing an operator could
trigger was a full cold rebuild.

    update -> propagate -> brief (stale leaves) -> brief-upper (stale uppers)
           -> monitor -> repair

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

from hrono.cluster.monitor import monitor
from hrono.cluster.repair import repair
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.summarize.brief import brief
from hrono.summarize.brief_upper import brief_upper
from hrono.summarize.propagate import propagate
from hrono.tree.settle import should_settle
from hrono.tree.update import update

_DEFAULT_TREE = "default"


def sync(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
    client: object | None = None,
    core_labeler: object | None = None,
) -> Mapping[str, object]:
    """Run the incremental chain over ``tree``; report what each stage did."""
    tree = job.tree or _DEFAULT_TREE
    update(
        _stage(tree, "update"),
        context,
        encoder_for=encoder_for,
        client=client,
    )
    judged = propagate(_stage(tree, "propagate"), context, client=client)
    brief(_stage(tree, "brief"), context, client=client)
    brief_upper(_stage(tree, "brief-upper"), context, client=client)
    monitor(_stage(tree, "monitor"), context)
    repair(_stage(tree, "repair"), context, core_labeler=core_labeler)
    with context.database.connect() as conn:
        settle_due = should_settle(conn, tree)
    return _outcome(judged, settle_due=settle_due)


def _outcome(
    judged: Mapping[str, object], *, settle_due: bool
) -> Mapping[str, object]:
    """What the run did, for the operator (#132).

    One verb over six stages is a black box unless it says what happened, which
    is the honest objection to this design and the thing that answers it.
    ``settle_due`` is the trigger INFORMING: hrono has not run it and will not.
    """
    return {
        "judged": judged.get("judged", 0),
        "propagated": judged.get("propagated", 0),
        "skipped": judged.get("skipped", 0),
        "abstained": judged.get("abstained", 0),
        "settle_due": settle_due,
        "incomplete": bool(judged.get("incomplete", False)),
    }


def _stage(tree: str, op: str) -> Job:
    return Job(
        id=f"sync-{op}",
        parent_id=None,
        tree=tree,
        op=op,
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


OPS["sync-tree"] = sync
