---
id: 184
title: non-tree edges on the graph — pull, proximity, propagation (T50.3)
priority: medium
size: medium
depends_on: [183, 089, 087]
spec_refs: [build-order.md#T50.3]
---

## Context
T50.3: "non-tree edges (sibling proximity, misfit-pull, propagation path)".
The graph (#183) draws the hierarchy, which is the one relationship the tree
already makes obvious. The relationships that explain why the tree is WRONG are
the ones nothing draws: a topic whose chunks belong next door, two siblings
that are really one topic, and the path a change climbed.

Two of the three need centroids, and centroids are leaf-only
(`cluster_store.node_centroids` reads `nodes ... level = 0`) and recomputed
from member vectors on every call. So:

- The overlays are **opt-in per URL** (`?edges=pull,proximity,propagation`),
  off by default. The default graph stays as fast as #183 made it, and every
  overlay is still a bookmarkable URL rather than client state.
- Centroids are computed for the **visible** topics only, not the tree.
- Pull and proximity are **level 0 only**, and the page says so. An upper-level
  centroid does not exist; proximity between briefs is a different question and
  is not this ticket.

## Description
- `pull` — for each visible leaf, the OTHER visible leaf whose centroid is
  nearer to some of its members, with how many. This is the misfit signal
  (#089) drawn as the edge it always was: `monitor._misfits` already makes this
  exact comparison and throws the winner away, keeping only a count.
  **The comparison must stay in one place** — one rule that both the health
  count and the drawn edge read, so the graph and the number cannot disagree.
- `proximity` — visible leaves that share a parent and whose centroids are at
  or above TAU: candidates for a merge.
- `propagation` — `update_log.climbed_to`: node -> where the cascade stopped,
  for the recent rows of this tree. Stored already; no vectors.
- No embedding model configured, or more than one and none named, is a
  DEGRADE, not a 500: draw the tree, say the overlay needs a model.

## Acceptance criteria
- [x] `?edges=` off by default; the default graph draws no extra edges and
      runs no vector work.
- [x] A pull edge appears for a leaf holding a chunk another visible leaf's
      centroid is nearer to, with REAL vectors, not planted similarities.
- [x] The pull comparison and the stored misfit count come from the same rule —
      changing the rule moves both.
- [x] A proximity edge appears between two near siblings and NOT between
      distant ones.
- [x] A propagation edge is drawn from a real `update_log` row.
- [x] Each edge kind is visually distinct and labelled in a legend.
- [x] With no embedding model, the page renders the tree and says the overlay
      is unavailable.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored. Split out of #183, which shipped T50.1/.2 only.
- 2026-09-27 dev: `server/overlays.py` (the three edge kinds), the `?edges=`
  parameter on the graph route, `link` lines + a legend + per-kind toggles in
  `graph.html`.
  - The pull comparison moved into `monitor.verdicts`: ONE `pulled =
    best_other > own`, read twice — once for the edge, once for the stored
    misfit count. `_misfits` is now a count over those verdicts.
  - `cluster_store.node_centroids` takes an optional `node_ids` bound, so the
    page asks for the handful of centroids it draws and gets the SAME centroid
    definition the monitor uses.
  - The candidate set is what is DRAWN: a pull points somewhere the operator
    can actually look, rather than at a topic `?open=` has collapsed.
  - Mutations, all killed: pull reversed; proximity without the shared-parent
    check; TAU dropped; `puller` kept when not nearer; `node_ids` bound
    ignored; overlay drawn when not asked; vector work done when not asked;
    and the shared `pulled` comparison broken (fails the overlay suite AND
    `tests/cluster/test_monitor.py` — which is the criterion).
  - Driven live on :8793: default page has no links; `pull`, `proximity`,
    `propagation` each draw exactly one; all three together draw three.
  - Gate: 1324 passed, 2 skipped.
- 2026-09-27 qa: verified, with one finding raised and fixed.
  - FINDING (fixed): proximity required a non-null shared parent, so a tree
    with no level above it — every tree between the first cluster build and the
    first brief pass — drew nothing, silently. That is precisely where a
    near-duplicate cluster is worth seeing. Two UNPARENTED leaves are siblings
    too; the rule is now "the same parent, `None` included". Mutations: the
    non-null requirement back -> the flat-tree test fails; the same-parent
    check dropped -> the different-parents test fails.
  - Added: the default page runs ZERO statements against `embeddings`, and so
    does `?edges=propagation` on its own — measured with a trace callback, not
    inferred from "no link was drawn", which would leave the cost in place.
  - The one-rule criterion is tested by mutation across two suites: breaking
    `pulled = best_other > own` fails BOTH `tests/server/test_ui_graph_overlays`
    and `tests/cluster/test_monitor`.
  - Noted, not fixed: `verdicts` is O(members x drawn topics). It is opt-in per
    URL and bounded by what is drawn, which is the reason it is opt-in.
  - Gate: 1325 passed, 2 skipped.
- 2026-09-27 po: accepted. T50 is complete. The qa finding is the right kind of
  catch — an overlay that draws nothing looks identical to a tree with nothing
  to say, and the difference matters most on a young tree.
