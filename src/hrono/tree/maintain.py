"""The ``maintain`` op (T24): run the whole pipeline in order over a tree.

One easy-button that drives the existing ops in dependency order — sync (#025)
-> split (#032) -> embed (#035) -> condense (#058) -> cluster (#040) -> brief
(#059) -> recurse-to-root (#062) — so a fresh tree builds all the way to a
single root. Stages run sequentially on the current jobs framework (no #051
DAG): the maintain job runs each op in turn, and a stage that raises fails the
maintain leaf, leaving nothing half-applied beyond the committed stages.

Incremental only where M4 allows it: embed (#035) and condense (#058) are
content-hash caches, so a second maintain re-embeds and re-condenses NOTHING.
The cluster/brief/brief-upper layers full-rebuild each run — ``cluster``
recreates nodes with fresh ids and ``briefs.node_id ON DELETE CASCADE`` wipes
the briefs — so the brief layer is not yet incremental; stable-id incremental
placement is M7 (#068), out of scope here.

The seams (``encoder_for``, ``client``, ``build``) thread the injectable
backends through so the automated gate drives the real op chain with a fake
embedder + fake LLM; production passes none and each op uses its real default.
Driving it against a real embedding model + LLM key + source repo is manual qa.
"""

from __future__ import annotations

import sqlite3

from hrono.cluster.op import cluster
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry.collections.trees import scoped_sources
from hrono.summarize.brief import brief
from hrono.summarize.build_tree import build_tree
from hrono.summarize.condense import condense
from hrono.summarize.resolve import resolve_text_model

_DEFAULT_TREE = "default"

# The roles this chain will ask for, in the order it asks for them.
_ROLES = ("condense", "brief", "brief-upper")


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
) -> None:
    """Build a tree end to end: ingest, embed, condense, cluster, brief."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        sources = scoped_sources(conn, tree)
        _require_models(conn)

    for name in sources:
        source_scope = {"type": "source", "name": name}
        sync(_stage(tree, "sync", source_scope), context)
        split_source(_stage(tree, "split", source_scope), context)

    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)
    condense(_stage(tree, "condense", {}), context, client=client)
    cluster(_stage(tree, "cluster", {}), context, build=build)
    brief(_stage(tree, "brief", {}), context, client=client)
    build_tree(
        _stage(tree, "build-tree", {}),
        context,
        client=client,
        encoder_for=encoder_for,
        build=build,
    )
    # brief + build-tree wrote node:// brief passages (#071) after the first
    # embed; vectorise them so recall's vector leg covers briefs too.
    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)


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
