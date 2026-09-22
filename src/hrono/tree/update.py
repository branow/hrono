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

A leaf the drain emits here is NOT parented, and not briefed either: both need
the brief pass this op deliberately does not run (``update`` makes no LLM calls
at all). #114's attach places a leaf by its BRIEF vector, so there is nothing to
place until something briefs it — the next ``settle`` or ``maintain`` briefs,
attaches and re-briefs its parent in one pass, and the drain's own churn is what
tends to trigger that settle. Until then the chunks are in a node and written to
the export, but unreachable from ``root.md``: better than parked and invisible,
worse than reachable, and bounded by the next brief pass. Briefing inside
``update`` is the same question #122 asks about condensing, and belongs there.

ONE BATCH NUMBER PER RUN, not per source (#099). ``tree_batch.batch`` is the
clock incubator ageing measures against (``current_batch - parked_at >
MAX_AGE``), so counting a run over three changed sources as three batches ages
parked chunks three times too fast — and a force-assigned member is never
revisited today (#113), which makes premature forcing permanent. The number is
allocated LAZILY, by the first source that actually has changes, so a run over
an unchanged corpus leaves the counter alone; every later source in the same
run reuses it. A RETRIED run — #093 reclaims a job stranded by a dead worker —
is a fresh run and allocates another batch: a retry genuinely is another pass
over the corpus, and per-job allocation state would be real machinery for
semantics that already read correctly, bounded at one extra tick against a
MAX_AGE tolerance of 5.

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
from hrono.ingest.split_op import _instance, _load
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

    batch: int | None = None
    for name in sources:
        sync(_stage(tree, "sync", {"type": "source", "name": name}), context)
        batch = _update_source(
            context, tree, name, model_name, encoder_for, batch
        )


def _update_source(
    context: JobContext,
    tree: str,
    name: str,
    model_name: str,
    encoder_for: object | None,
    batch: int | None,
) -> int | None:
    """Apply one source's delta; return the run's batch, allocating it once.

    ``batch`` is the number already allocated by an earlier source in THIS run,
    or None if nothing has changed yet — a source with no changes passes it
    straight through, so a run over an unchanged corpus never touches the
    counter at all.
    """
    config, version = _load(context, name)
    raw_filter = config.get("filter")
    filter_config = raw_filter if isinstance(raw_filter, dict) else None
    cache = context.cache_for(name)
    with context.database.write() as conn:
        changes = diff.diff(conn, name, cache, filter_config)
        if not changes:
            return batch
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
        current = _next_batch(conn, tree) if batch is None else batch

    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)

    with context.database.write() as conn:
        placement.place(conn, tree, deltas, centroids, model_name, current)
        incubator.age(conn, tree, model_name, current)
    incubator.drain(context.database, tree, model_name)
    return current


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
