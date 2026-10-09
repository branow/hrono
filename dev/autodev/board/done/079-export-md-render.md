---
id: 079
title: MD render of the agent-facing tree — brief, mechanical child listings, Caution, section reassembly (T30)
priority: high
size: big
depends_on: [078, 032, 059, 061]
spec_refs: [build-order.md#T30, how-hrono-works.md]
---

## Context
T30 renders the collapsed agent-facing tree (#078) into the markdown an agent
walks: descending it, the root brief orients, each level's briefs say what lives
below, the Caution sections warn about hazards before any source is opened, and
at the bottom the agent reads whole sections reassembled byte-identically from
passages. Child listings are MECHANICAL — rendered from the stored tree at export
time, never written by an LLM — so navigation never depends on a hallucinated
link.

## Description
Produce, per agent-facing node, the MD content + its file path in the tree:
- **Brief**: the node's stored brief text (#059/#061), which already ends with a
  Caution section (aggregated GOTCHA lines) — render it as-is; do NOT regenerate.
- **Child listings MECHANICAL**: list the node's children (title + relative path)
  from the collapsed tree in code — no LLM, no hallucinated links. This is the
  navigation.
- **Leaves = whole sections**: at the bottom, render each section reassembled
  byte-identically from its stored passages (#032 proves section == concat of its
  passages), with its address/provenance header so the agent can reach the
  original file.
- **Notes (render-if-present)**: human annotations are export-visible
  (implementation-notes) — render a node/section's notes if any exist; notes
  CREATION is M9, so for M6 just render them when present, do not build the notes
  store here.
- Output shape: a mapping of agent-facing tree path -> MD content (one file per
  node/leaf, e.g. `root.md`, `<topic>/brief.md`, `<topic>/<section>.md`), so #081
  can materialize a folder tree. Pure (no I/O, no LLM).

## Acceptance criteria
- [ ] Each agent-facing node renders its stored brief (incl. its Caution section)
      + a MECHANICAL child listing (titles + relative paths), no LLM text.
- [ ] Leaf sections render reassembled byte-identically from their passages, with
      address/provenance; a rendered section == the stored section bytes.
- [ ] Notes render when present; absent notes render nothing (no M9 dependency).
- [ ] Output is a deterministic path -> MD-content mapping for #081 to write.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The collapse algorithm (#078), the endpoint (#080), the CLI/disk write (#081).
- Notes creation/storage (M9) — render-if-present only.
- Regenerating briefs or Caution — render stored text as-is.

## Review log
- 2026-08-25 PO: authored as T30. Renders #078's collapsed tree to MD — stored
  brief (with its Caution), mechanical child listings (no hallucinated links),
  byte-identical section reassembly at the leaves, notes-if-present. Emits a
  path->content mapping so #081 writes a folder tree.
- 2026-08-25 dev: DONE, committed 7c063d5 (+ style 6183736), handoff to qa.
  `export/render.py` `render(conn, ExportTree, *, notes=None) -> {path: md}` (no
  file I/O). Per agent node: stored brief text as-is (its Caution included, never
  regenerated) + a MECHANICAL child listing (heading + relative link built in
  code); leaf nodes list their sections. Each section renders to its own file,
  reassembled byte-identically from its stored passages (#032) with a path/uri
  header. Notes render only when passed (M9 seam; no notes store built). Paths:
  root -> root.md, node -> <slug-chain>/brief.md, section -> <slug-chain>/
  <slug>-<id>.md. Added `export/store.load(conn, tree) -> StoredTree` (nodes +
  node_children + node_members, root = highest level) for #080.
  Verified: ruff clean; pytest 517 passed / 1 skip (+5: root brief + mechanical
  child links, leaf section listing + Caution carried, section reassembles
  byte-identically == stored section bytes, notes-if-present, deterministic).
  Feeds #080 endpoint.
- 2026-08-25 qa: FAIL -> back to todo. The render is correct for distinct-heading
  trees, but node DIRECTORY names collide on duplicate brief headings, silently
  DROPPING a whole subtree from the export — a data-loss bug:
    - `_name(node)` = `_slug(_heading(node))` with NO node id (unlike
      `_section_name`, which appends `-{id}`). Two sibling nodes whose brief first
      lines slug to the same value (e.g. both "# Overview") get the same directory,
      so both render to the same `overview/brief.md` and the second OVERWRITES the
      first in the returned `{path: md}` dict.
    - Reproduced: root with two children whose briefs both start "# Overview" ->
      `render` returns only `['overview/brief.md', 'root.md']`; child A's brief is
      GONE (its subtree/sections drop out of the export entirely), and the root's
      two mechanical child links BOTH point at `overview/brief.md` (broken/ambiguous
      navigation).
    - LLM briefs readily produce duplicate headings ("Overview", "Summary",
      "Authentication", ...), so sibling heading collisions are realistic, not
      theoretical — and this is the MVP export an agent walks, so a vanished topic
      is a trust/correctness failure.
  What must change: make node directory names collision-safe the same way sections
  already are — include the node id in `_name`/`_directory` (e.g. `<slug>-<id>`),
  so every agent node maps to a unique path and each mechanical child link is
  unique. Add a regression test with two same-heading siblings asserting both
  subtrees survive and their links differ. Everything else passes and needs no
  change: byte-identical section reassembly (concat passages by ordinal,id per
  #032), stored brief rendered as-is with its Caution, mechanical child/section
  listings, notes-if-present, determinism; ruff + the other export tests are green.
  Minor (non-blocking, address if convenient): the `notes` seam is keyed by node
  id and only rendered in `_node_markdown`; the ticket says "node/section notes",
  so SECTION notes have no seam. No notes exist in M6 (creation is M9), so this is
  a forward-seam gap only — widen it to sections when M9 lands if not now.
  NOTE: this ticket's dependency #078 is still in todo (my earlier levels<2 bounce);
  079's render logic is independent of that fix (it consumes an ExportTree, whose
  shape is unaffected for valid levels), so I reviewed 079 on its own merits.
- 2026-08-25 dev: FIXED qa bounce, committed 95394ce, handoff to qa. `_name` now
  suffixes the node id (`<slug>-<id>`), the same collision-safety sections already
  had, so two siblings whose briefs share a heading (LLM briefs repeat "Overview"
  etc.) map to distinct directories — no subtree is dropped and every mechanical
  child link is unique. Added a regression test: two same-heading "# Overview"
  siblings -> both subtrees survive, two distinct child links. Updated the render
  tests for the id-suffixed dirs. Everything qa passed is unchanged. Verified:
  ruff clean; pytest 519 passed / 1 skip.
- 2026-08-25 qa: PASS -> po-review. Re-verified the collision fix by re-running my
  exact repro: a root with two children whose briefs both start "# Overview" now
  renders `overview-2/brief.md` AND `overview-3/brief.md` — both subtrees survive
  (child A and child B briefs both present) and the root's two mechanical child
  links are distinct. Dev's regression test `test_same_heading_siblings_do_not_
  collide` pins it. The fix only touched `_name`, so everything I verified before
  is unchanged (byte-identical section reassembly, stored-brief-as-is + Caution,
  mechanical listings, notes-if-present, determinism). ruff clean; full suite 519
  passed / 1 skip; tree clean, committed 95394ce. Dependency #078's levels-clamp
  fix is now also PASSED (po-review). Non-blocking forward note stands: the
  render-if-present `notes` seam covers nodes only, not sections — fine for M6
  (notes creation is M9); widen to sections when M9 lands. (Pre-existing
  `.gitignore` edit still uncommitted.)
- 2026-08-25 PO review: PASS -> done. Gated #079's commit (95394ce) in an isolated
  worktree (tree carried #080 endpoint WIP): ruff clean, 14 export tests pass.
  The qa-caught collision was a genuine data-loss bug (two sibling briefs sharing
  a heading -> same dir slug -> one overwrites the other in the {path:md} dict ->
  a whole subtree vanishes from the MVP export an agent walks); dev's `<slug>-<id>`
  suffix (the same collision-safety sections already had) fixes it, verified with
  the exact two-"# Overview" repro. Confirmed the render is correct: stored brief
  as-is WITH its Caution (never regenerated), MECHANICAL child listings (heading +
  relative link in code, no LLM), leaf sections reassembled BYTE-IDENTICALLY from
  passages (#032 invariant preserved), notes-if-present, deterministic path->md
  mapping. All acceptance criteria met. Closed. Forward note for M9 (recorded, no
  ticket yet — M9 unauthored): when notes creation lands, widen the render's
  render-if-present `notes` seam from nodes to sections too.
