"""The ``maintain`` op: run the whole pipeline in order over a tree.

One easy-button that drives the existing ops in dependency order — sync
-> split -> embed -> condense -> embed the condensations -> cluster -> brief
 -> recurse-to-root — so a fresh tree builds all the way to a
single root. Stages run sequentially on the current jobs framework (no DAG
scheduler): the maintain job runs each op in turn, and a stage that raises fails
the maintain leaf, leaving nothing half-applied beyond the committed stages.

Embed and condense are content-hash caches, so a second maintain re-embeds and
re-condenses NOTHING. The cluster layer re-clusters every run, but
``replace_tree`` keeps the id — and so the brief — of every cluster whose
content is unchanged. Incremental placement is the ``update`` op's job.

The seams (``encoder_for``, ``client``, ``build``) thread the injectable
backends through so the automated gate drives the real op chain with a fake
embedder + fake LLM; production passes none and each op uses its real default.
Driving it against a real embedding model + LLM key + source repo is a manual
check.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from hrono.cluster.op import cluster
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.health import report
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.stages import Stages
from hrono.registry.collections.trees import DEFAULT_TREE, ingest_sources
from hrono.registry.completeness import BUILD_ROLES
from hrono.summarize.brief import brief
from hrono.summarize.build_tree import build_tree
from hrono.summarize.condense import condense
from hrono.summarize.resolve import resolve_text_model
from hrono.tree import changes
from hrono.tree.settle import anchor_members, restore_pinned

# The roles this chain will ask for, in the order it asks for them — the same
# tuple Settings checks before anyone starts a build.
_ROLES = BUILD_ROLES


def _require_models(conn: sqlite3.Connection) -> None:
    """Fail before the expensive stages, not after them.

    `maintain` clones, splits and embeds the whole corpus before the first
    model call. Reaching `llm-error: no text model available` there costs
    minutes of work to learn something knowable at second zero — so the roles
    are resolved up front, through the SAME resolver the stages use, and the
    op stops with the same error it would have raised later.

    Unconditional, including when a `client` is injected: the STAGES resolve
    these models whatever completion they are handed — `condense` asks for its
    text model before it checks whether there is anything to condense — so this
    adds no requirement the chain did not already have. It only moves the
    failure to before the work instead of after it.
    """
    resolve_embedding_model(conn, {})
    for role in _ROLES:
        resolve_text_model(conn, {}, role)


def maintain(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
    client: object | None = None,
    build: object | None = None,
) -> Mapping[str, object]:
    """Build a tree end to end: ingest, embed, condense, cluster, brief.

    Every stage is timed and its counts kept, and a failing one is
    reported by name with the item it was on and the stages before it.
    """
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        sources = ingest_sources(conn, tree)
        _require_models(conn)
        before = changes.snapshot(conn, tree)

    run = Stages()
    for name in sources:
        source_scope = {"type": "source", "name": name}
        run.run(
            "sync",
            lambda s=source_scope: sync(_stage(tree, "sync", s), context),
            over=name,
        )
        run.run(
            "split",
            lambda s=source_scope: split_source(
                _stage(tree, "split", s), context
            ),
            over=name,
        )
    with context.database.connect() as conn:
        anchored = anchor_members(conn, tree)
    run.run(
        "embed",
        lambda: embed(
            _stage(tree, "embed", {}), context, encoder_for=encoder_for
        ),
    )
    run.run(
        "condense",
        lambda: condense(_stage(tree, "condense", {}), context, client=client),
    )
    # clustering reads a section by its condensation's vector, so the
    # condensations just written are embedded before it runs
    run.run(
        "embed-condensations",
        lambda: embed(
            _stage(tree, "embed", {}), context, encoder_for=encoder_for
        ),
    )
    run.run(
        "cluster",
        lambda: cluster(_stage(tree, "cluster", {}), context, build=build),
    )

    # the full rebuild re-assigned every membership by machine judgement, so a
    # hand-placed chunk goes back where its pin holds it BEFORE brief writes
    # summaries over membership — the same move `settle` makes, for the same
    # reason. WHERE each pin points is read after the split (which re-pinned
    # the re-minted section ids) and before the cluster (which erases the
    # membership the anchor's company is recovered from).
    def _restore() -> Mapping[str, int]:
        with context.database.write() as conn:
            held, released = restore_pinned(conn, tree, anchored)
        return {"held": held, "released": released}

    run.run("restore-pins", _restore)
    run.run(
        "brief",
        lambda: brief(_stage(tree, "brief", {}), context, client=client),
    )
    run.run(
        "build-tree",
        lambda: build_tree(
            _stage(tree, "build-tree", {}),
            context,
            client=client,
            encoder_for=encoder_for,
            build=build,
        ),
    )
    # brief + build-tree wrote node:// brief passages after the first
    # embed; vectorise them so recall's vector leg covers briefs too.
    run.run(
        "embed",
        lambda: embed(
            _stage(tree, "embed", {}), context, encoder_for=encoder_for
        ),
    )
    run.run("health", lambda: report.refresh(context.database, tree))
    with context.database.connect() as conn:
        changed = changes.since(conn, tree, before)
    return run.outcome({"tree": changed})


def _stage(tree: str, op: str, scope: dict[str, object]) -> Job:
    return Job(
        id=f"maintain-{op}",
        parent_id=None,
        tree=tree,
        op=op,
        scope=scope,
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


OPS["maintain"] = maintain
