"""The incremental ``update`` op: apply a change batch, no rebuild.

hrono's differentiator in its efficient form. Where ``maintain`` full-rebuilds
the cluster level each run (keeping stable ids via the signature reconcile),
``update`` touches only the delta: per source it syncs, classifies the file
diff, reconciles just the changed files' sections, embeds the new content (the
content-hash cache re-embeds nothing unchanged), then applies the placement rule
against the PRE-BATCH cluster centroids. UMAP/HDBSCAN never run, so untouched
chunks never move: churn = changed content.

Placement is also the batch's pool pass: whatever it parks in the incubator
is drained (a pool big enough to cluster forms new topics) and then homed
(everything left joins its nearest topic, flagged ``forced``), so no section
is left outside the tree when the run ends.

A leaf the drain emits here is NOT parented, and not briefed either: both need
the brief pass this op deliberately does not run (``update`` makes no LLM calls
at all). Attach-by-proximity places a leaf by its BRIEF vector, so there is
nothing to place until something briefs it — ``sync-tree``'s closing ``adopt``
stage does exactly that in the same run (brief, attach, re-brief the parent), so
a leaf born here is reachable by the time the sync that made it returns. Only a
bare ``update`` job leaves it for the next sync, settle or maintain. Briefing
inside ``update`` is the same question the sync chain answers for condensing,
and belongs there.

CONDENSES WHAT IT INGESTS. Were ``maintain`` its only caller, every section an
incremental update brought in would reach the tree with no condensation until
somebody ran a full build — and a brief reduces over condensations while its
reference list does not, so the brief would cite sources it had never read.
Condensing here costs one call per genuinely NEW section (``condense`` is a
content-hash cache) and nothing for unchanged content, so it is proportional to
the change and the incremental promise holds. It runs once per RUN, after every
source has been reconciled, and only when a source actually reported changes.
That guard is not an optimization: ``condense`` resolves the text model BEFORE
it looks at what is pending, so an unguarded call makes `hrono update` fail with
"no text model available" on a fresh install with no sources and nothing to do —
an error naming a stage the user never asked for, from a run that should have
been a no-op. The cost is that a corpus carrying OLD gaps heals them on the next
run WITH changes rather than on any run at all, which is a wait, not a hole.

The one exception is a stored condensation that is the model TALKING BACK:
``unusable-condensations`` promises the next sync re-condenses exactly
those, and on an unchanged corpus — the usual state of a tree an operator is
asking that of — the guard above alone means no sync ever does. So the
stage also runs when the condense model has one; with no condense model there
is nothing stored under it to redo, and the no-op run still asks for nothing.
A talk-back the model has already refused to redo for the same model and
prompt does not count: it stays listed, and the next try waits for its
body, the model or the prompt to change, rather than costing two calls on
every sync of a steady tree.

Accepting LLM calls inside ``update`` is deliberate: the
promise is that work is proportional to the change, not that the op is free —
and the alternative left a leaf with no condensation, therefore no brief,
therefore no brief vector, therefore no parent.

ONE BATCH NUMBER PER RUN, not per source: ``tree_batch.batch`` stamps the
chunks a run parks, so one run over three changed sources is one batch. The
number is allocated LAZILY, by the first source that actually has changes, so a
run over an unchanged corpus leaves the counter alone; every later source in the
same run reuses it. A RETRIED run — the worker reclaims a job stranded by a dead
worker — is a fresh run and allocates another batch.

Lock discipline like the other ops: the diff + centroid snapshot + section
reconcile run under one write lock (so the centroids are consistently
pre-batch), embed runs its heavy compute under its own lock, then placement
re-acquires to persist placement and ageing (dot products only). The drain owns
its own locks — its mini-pipeline is real UMAP -> HDBSCAN, so it runs outside
this one. The ``encoder_for`` seam threads the injectable embedder through for
the automated gate; production passes none.
"""

from __future__ import annotations

from collections.abc import Mapping

from hrono.cluster import ClusterError, TooFewPoints, incubator, placement
from hrono.cluster import store as cluster_store
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.ingest import diff, reconcile
from hrono.ingest.readers import resolve
from hrono.ingest.split_op import _load
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import LLMError
from hrono.registry.collections.trees import DEFAULT_TREE, ingest_sources
from hrono.summarize import store as condensations
from hrono.summarize.condense import condense
from hrono.summarize.resolve import resolve_prompt, resolve_text_model


def update(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
    client: object | None = None,
) -> Mapping[str, object]:
    """Apply each source's change batch incrementally to the tree."""
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        sources = ingest_sources(conn, tree)
        model_name = str(resolve_embedding_model(conn, job.scope)["name"])

    batch: int | None = None
    deferred = 0
    for name in sources:
        sync(_stage(tree, "sync", {"type": "source", "name": name}), context)
        batch, held = _update_source(
            context, tree, name, model_name, encoder_for, batch
        )
        deferred += held
    rescued, batch = _rescue(
        context, tree, sources, model_name, encoder_for, batch
    )
    condensed = None
    if batch is not None or _talked_back(context):
        condensed = condense(
            _stage(tree, "condense", {}), context, client=client
        )
    return _outcome(context, tree, batch, condensed, rescued, deferred)


def _talked_back(context: JobContext) -> bool:
    """Is there a reply that talked back this request may still redo?

    One already refused for the same model and prompt is not: a sync
    over an unchanged corpus would otherwise pay two calls for it every time.
    """
    with context.database.connect() as conn:
        try:
            model = resolve_text_model(conn, {}, "condense")
            _, template = resolve_prompt(conn, "condense")
        except LLMError:
            return False  # no condense model: nothing stored under it to redo
        request = condensations.request_for(model, template)
        return bool(condensations.redo(conn, str(model["name"]), request))


def _outcome(
    context: JobContext,
    tree: str,
    batch: int | None,
    condensed: Mapping[str, object] | None,
    rescued: int,
    deferred: int,
) -> Mapping[str, object]:
    """What this run changed, for the operator rather than the log.

    ``forced`` is the count that matters: a force-assign is the system deciding
    that an alien member is better than an unreachable one — a real
    judgement call, and must not be a silent one. ``parked`` is its counterpart,
    chunks still waiting outside the tree. ``condense`` is what the condense
    step did and spent, present when it ran: without it, a sync over an
    unchanged tree that redid talked-back condensations would say
    ``changed: false`` and nothing else, its calls showing only in the run's
    usage.
    """
    spent: dict[str, object] = (
        {} if condensed is None else {"condense": dict(condensed)}
    )
    if rescued:
        spent["rescued"] = rescued
    if deferred:
        spent["drain_deferred"] = deferred
    if batch is None:
        return {"changed": False, "batch": None, **spent}
    with context.database.connect() as conn:
        forced = int(
            conn.execute(
                "SELECT COUNT(*) FROM node_members m "
                "JOIN nodes n ON n.id = m.node_id "
                "WHERE n.tree = ? AND m.forced = 1",
                (tree,),
            ).fetchone()[0]
        )
        parked = int(
            conn.execute(
                "SELECT COUNT(*) FROM pending WHERE tree = ?", (tree,)
            ).fetchone()[0]
        )
    return {
        "changed": True,
        "batch": batch,
        "forced": forced,
        "parked": parked,
        **spent,
    }


def _update_source(
    context: JobContext,
    tree: str,
    name: str,
    model_name: str,
    encoder_for: object | None,
    batch: int | None,
) -> tuple[int | None, int]:
    """Apply one source's delta; return (run batch, drains deferred).

    ``batch`` is the number already allocated by an earlier source in THIS run,
    or None if nothing has changed yet — a source with no changes passes it
    straight through, so a run over an unchanged corpus never touches the
    counter at all.
    """
    config, version = _load(context, name)
    cache = context.cache_for(name)
    reader, addressed, instance = resolve(config, cache)
    with context.database.write() as conn:
        changes = diff.diff(conn, name, reader, config, cache)
        if not changes:
            return batch, 0
        centroids = cluster_store.node_centroids(conn, tree, model_name)
        deltas = reconcile.reconcile(
            conn,
            tree=tree,
            source=name,
            source_type=addressed,
            instance=instance,
            version=version,
            fetch=lambda path: reader.unit(config, cache, path),
            changes=changes,
        )
        current = _next_batch(conn, tree) if batch is None else batch

    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)

    with context.database.write() as conn:
        placement.place(conn, tree, deltas, centroids, model_name, current)
    deferred = _drain(context, tree, model_name)
    with context.database.write() as conn:
        cluster_store.backfill_coords(conn, tree, model_name)
    return current, deferred


def _drain(context: JobContext, tree: str, model_name: str) -> int:
    """Drain the pool, then home what is left; count a deferred drain.

    ``drain``'s mini-pipeline raises ``ClusterError`` on input UMAP cannot
    reduce — tied or identical vectors. It must not propagate out of
    ``update``: placement has already committed, so it would fail the whole
    sync at a stage that had already done its work, on every later run too,
    since the pool stays exactly as degenerate. A pool that cannot be
    clustered is homed instead, and the outcome says the drain was deferred.
    """
    deferred = 0
    try:
        incubator.drain(context.database, tree, model_name)
    except TooFewPoints:
        raise
    except ClusterError:
        deferred = 1
    with context.database.write() as conn:
        incubator.home(conn, tree, model_name)
    return deferred


def _rescue(
    context: JobContext,
    tree: str,
    sources: tuple[str, ...],
    model_name: str,
    encoder_for: object | None,
    batch: int | None,
) -> tuple[int, int | None]:
    """Park any section of this tree's sources that is in NO node and NOT
    pending; return (how many, the run batch).

    The crash-shaped hole this closes: ``_update_source`` commits the reconcile
    (old sections dropped, new ones inserted) in its first write block, then
    embeds, then places. A failure between the first commit and placement — a
    remote encoder down, a dims mismatch, the process dying — loses the deltas,
    and the next run's diff sees stored == current and reports nothing to do.
    Those sections were in no node and no pool, permanently, and only a full
    maintain would have found them. Parking them re-enters them through the
    pool's drain and home, so every run heals whatever an earlier run left
    homeless.
    """
    if not sources:
        return 0, batch
    marks = ",".join("?" * len(sources))
    with context.database.write() as conn:
        rows = conn.execute(
            f"SELECT id FROM sections s WHERE s.source IN ({marks}) "  # noqa: S608
            "AND s.source_type != 'node' AND NOT EXISTS ("
            "SELECT 1 FROM node_members m JOIN nodes n ON n.id = m.node_id "
            "WHERE m.section_id = s.id AND n.tree = ?) AND NOT EXISTS ("
            "SELECT 1 FROM pending p WHERE p.section_id = s.id "
            "AND p.tree = ?) ORDER BY s.id",
            (*sources, tree, tree),
        ).fetchall()
        homeless = [int(row["id"]) for row in rows]
        if not homeless:
            return 0, batch
        current = _next_batch(conn, tree) if batch is None else batch
        for section_id in homeless:
            incubator.park(conn, tree, section_id, current)
    embed(_stage(tree, "embed", {}), context, encoder_for=encoder_for)
    _drain(context, tree, model_name)
    return len(homeless), current


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
