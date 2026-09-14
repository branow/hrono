"""The incremental ``update`` op (#085, T34): apply a change batch, no rebuild.

hrono's differentiator in its efficient form. Where ``maintain`` full-rebuilds
the cluster level each run (keeping stable ids via #068), ``update`` touches
only the delta: per source it syncs, classifies the file diff (#083), reconciles
just the changed files' sections (#085 reconcile), embeds the new content (the
#035 content-hash cache re-embeds nothing unchanged), then applies the
placement rule against the PRE-BATCH cluster centroids (#085 placement).
UMAP/HDBSCAN never run, so untouched chunks never move: churn = changed content.

Placement is also the batch's pool pass (#095): whatever it parks in the
incubator (#086) is immediately aged — anything past ``MAX_AGE`` batches is
force-assigned — and then drained, so a chunk is never pending for longer than
the pool can justify. Age runs first: the drain re-homes the whole pool anyway,
so ageing after it would only re-decide chunks the drain already placed.

Lock discipline like the other ops: the diff + centroid snapshot + section
reconcile run under one #008 write lock (so the centroids are consistently
pre-batch), embed runs its heavy compute under its own lock, then placement
re-acquires to persist placement and ageing (dot products only). The drain owns
its own locks — its mini-pipeline is real UMAP -> HDBSCAN, so it runs outside
this one. The ``encoder_for`` seam threads the injectable embedder through for
the automated gate; production passes none.
"""

from __future__ import annotations

from hrono.cluster import incubator, placement
from hrono.cluster import store as cluster_store
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.ingest import diff, reconcile
from hrono.ingest.split_op import _CACHE_ROOT, _instance, _load
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store

_DEFAULT_TREE = "default"


def update(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
) -> None:
    """Apply each source's change batch incrementally to the tree."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        sources = [
            row["name"] for row in registry_store.list_all(conn, "sources")
        ]
        model_name = str(resolve_embedding_model(conn, job.scope)["name"])

    for name in sources:
        sync(_stage(tree, "sync", {"type": "source", "name": name}), context)
        _update_source(context, tree, name, model_name, encoder_for)


def _update_source(
    context: JobContext,
    tree: str,
    name: str,
    model_name: str,
    encoder_for: object | None,
) -> None:
    config, version = _load(context, name)
    raw_filter = config.get("filter")
    filter_config = raw_filter if isinstance(raw_filter, dict) else None
    cache = _CACHE_ROOT / name
    with context.database.write() as conn:
        changes = diff.diff(conn, name, cache, filter_config)
        if not changes:
            return
        centroids = cluster_store.node_centroids(conn, tree, model_name)
        deltas = reconcile.reconcile(
            conn,
            tree=tree,
            source=name,
            source_type=str(config["type"]),
            instance=_instance(str(config["url"])),
            version=version,
            cache=cache,
            changes=changes,
        )
        batch = _next_batch(conn, tree)

    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)

    with context.database.write() as conn:
        placement.place(conn, tree, deltas, centroids, model_name, batch)
        incubator.age(conn, tree, model_name, batch)
    incubator.drain(context.database, tree, model_name)


def _next_batch(conn: object, tree: str) -> int:
    row = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO tree_batch(tree, batch) VALUES (?, 1) "
        "ON CONFLICT(tree) DO UPDATE SET batch = batch + 1 RETURNING batch",
        (tree,),
    ).fetchone()
    return int(row["batch"])


def _stage(tree: str, op: str, scope: dict[str, object]) -> Job:
    return Job(
        id=f"update-{op}",
        parent_id=None,
        tree=tree,
        op=op,
        scope=scope,
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


OPS["update"] = update
