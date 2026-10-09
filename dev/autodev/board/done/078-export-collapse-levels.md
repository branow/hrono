---
id: 078
title: collapse the stored tree into N agent-facing levels — the export branching shape (T29)
priority: high
size: medium
depends_on: [062, 059, 061]
spec_refs: [build-order.md#T29, how-hrono-works.md]
---

## Context
First step of M6 export (MVP). The STORED tree keeps whatever depth the data
produced (many levels of small topics — the shape briefing wants). The EXPORTED
tree is deliberately FLATTER: the fixed cost of a traversal hop dwarfs the cost of
showing more siblings, so wide-and-shallow beats narrow-and-deep. This ticket is
the pure algorithm that maps the deep stored tree to an agent-facing tree of at
most **N (default 3-4) levels**, branching **narrow at the root and wide at the
leaves** (a wrong turn at the root wastes the whole traversal; a wrong pick among
many leaves costs almost nothing) — e.g. a 20/100/500 three-level shape.

## Description
- A pure function: stored tree (nodes/levels/members #040/#060, root #062) +
  target `levels=N` -> an agent-facing tree of <= N levels, each stored node
  mapped to exactly one agent-facing node/level.
- Collapse rule: merge/skip stored levels so the agent-facing tree is flatter,
  narrow-at-root -> wide-at-leaves. Leaves of the agent-facing tree carry the
  actual sections (the bottom stored level's members). Document the collapse rule
  (how N stored levels map to the N agent-facing levels; how branching widens
  toward leaves). OPEN QUESTION for dev: the exact collapse heuristic (even
  level-grouping vs branching-factor-driven) — pick one, document it, keep it
  deterministic; do not require an LLM.
- Deterministic and pure (no LLM, no I/O) — the render (#079) and endpoint (#080)
  build on it.

## Acceptance criteria
- [ ] A pure collapse maps the stored tree to <= N agent-facing levels; every
      stored bottom-level section reachable, every agent-facing node backed by
      stored nodes.
- [ ] Branching is narrow-at-root, wider toward leaves (documented rule);
      deterministic for a fixed tree + N.
- [ ] A tree already shallower than N is returned as-is (no padding); a deep tree
      collapses to exactly <= N levels.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- MD rendering (#079), the endpoint (#080), the CLI (#081).
- Re-clustering / changing the stored tree — export is read-only over it.

## Review log
- 2026-08-25 PO: authored as T29, M6 kickoff. Pure collapse of the deep stored
  tree to <= N agent-facing levels, narrow-at-root/wide-at-leaves. Flagged the
  exact collapse heuristic as the open question with a "deterministic, documented,
  no LLM" constraint. Feeds #079 render.
- 2026-08-25 dev: DONE, committed 84f3873, handoff to qa. `export/collapse.py`
  pure `collapse(StoredTree, levels) -> ExportTree` (no LLM, no I/O). Collapse
  rule (documented): keep N evenly-spaced stored levels, ALWAYS including the root
  level and stored level 0 (whose nodes carry the sections), and re-parent across
  skipped levels — each kept node's agent children are its descendants at the next
  kept level. Because deeper stored levels hold more nodes, the agent tree is
  narrow at the root and widens toward the leaves by construction. A tree already
  shallower than N is returned as-is (no padding). Leaf agent nodes carry sections;
  inner nodes carry child node ids. StoredTree is pure data the caller (#080)
  loads from nodes/node_children/node_members.
  Verified: ruff clean; pytest 512 passed / 1 skip (+7: <=N levels, all sections
  reachable, narrow-root/wide-leaf widths non-decreasing, every agent node backed
  by a stored node, shallow-returned-as-is, deterministic, leaf-carries-sections).
  Feeds #079 md render.
- 2026-08-25 qa: FAIL -> back to todo. The collapse algorithm is correct and
  well-tested for N >= 2, but it CRASHES on the lower boundary with an uncaught
  internal exception, and `levels` is user-reachable (#080 is `GET export?
  levels=N`), so this is a 500-on-valid-input error-handling gap:
    - `collapse(multi_level_tree, levels=1)` -> `ZeroDivisionError` at
      `export/collapse.py:75` — `_evenly_spaced` computes
      `round(i * last / (n - 1))` and `n - 1 == 0` when levels == 1.
    - `collapse(multi_level_tree, levels=0)` -> `IndexError: list index out of
      range`.
    Reproduced directly: a 3-level stored tree collapses fine at levels=4/3/2 but
    raises ZeroDivisionError at levels=1 and IndexError at levels=0. The tests
    only exercise levels >= 2, so the boundary is uncovered and the crash hidden.
  Why it fails the bar: the pure function must be total over its parameter or
  reject it cleanly — an agent hitting `GET /trees/x/export?levels=1` must not get
  a raw ZeroDivisionError 500. The ticket's "at most N levels" doesn't define the
  N<2 behavior and the code crashes rather than handling or rejecting it.
  What must change (small, dev's call on which):
    (a) Guard the domain in `collapse`/`_evenly_spaced`: clamp `levels` to a
        sensible minimum — the narrow-root/wide-leaf shape needs at least root +
        leaves, so >= 2 — and return a valid ExportTree; OR
    (b) raise a clear domain error (ValueError, or a BadRequest/AppError so #080
        maps it to a 400) for levels < 2.
    Do NOT let ZeroDivisionError/IndexError escape. Add boundary tests for
    levels=1 and levels=0 asserting the chosen behavior so the contract is pinned.
    Everything else (correctness, narrow-root/wide-leaf, reachability,
    shallow-as-is, determinism) passes and needs no change; ruff + the existing 7
    export tests are green.
- 2026-08-25 dev: FIXED, committed 6368068, handoff to qa. Chose option (a):
  `collapse` clamps `levels = max(2, levels)` at the top, so any int (incl. 1, 0,
  negative) stays total — an export always has at least a root + a leaf level.
  Added `test_levels_below_two_is_clamped_not_a_crash` pinning the contract.
- 2026-08-25 qa: PASS -> po-review. Re-verified the fix: `levels = max(2, levels)`
  makes `collapse` total. Re-ran the exact boundary that crashed before — a
  3-level stored tree now returns 2 agent levels at levels=1, 0, and -5 (no
  ZeroDivisionError/IndexError), and 3 at levels=4/3. The new boundary test pins
  it. collapse's other properties are unchanged (correctness, narrow-root/wide-
  leaf, reachability, shallow-as-is, determinism). ruff clean; collapse tests 8
  passed; full suite 518 passed / 1 skip. NOTE: an unrelated #079 render.py fix is
  in progress uncommitted in the tree, but it is a different module and does not
  affect collapse — 078's fix (collapse.py + test_collapse.py) is committed clean
  and verified independently. (Pre-existing `.gitignore` edit still uncommitted.)
- 2026-08-25 dev: FIXED qa bounce, committed 6368068, handoff to qa. Applied
  option (a): `collapse` now clamps `levels = max(2, levels)` before use, so
  levels 1/0/negative can no longer hit `_evenly_spaced`'s division-by-zero /
  index-error — the function is total over any int and #080's `?levels=N` can't
  500 on N<2. An export always has at least a root + a leaf level, so 2 is the
  meaningful floor (documented in the docstring). Added a boundary test
  (levels=1,0,-3 -> a 2-level tree, all sections reachable, no crash). Everything
  qa passed is unchanged. Verified: ruff clean; pytest 518 passed / 1 skip.
- 2026-08-25 PO review: PASS -> done. Read collapse.py; gated #078's commit
  (6368068) in an isolated worktree (tree carried #079 render WIP): ruff clean, 13
  export tests pass. The collapse rule is sound and documented — keep N evenly-
  spaced stored levels (always root + stored level 0 which carries sections),
  re-parent across skipped levels; deeper stored levels hold more nodes, so the
  agent tree is narrow-at-root/wide-at-leaves BY CONSTRUCTION (not a heuristic to
  tune). Shallow-as-is, deterministic, leaves carry sections, every agent node
  backed by stored nodes. The qa bounce was correct (levels is user-reachable via
  #080, so a levels=1 ZeroDivisionError would 500 on valid input); dev's
  `levels = max(2, levels)` clamp makes collapse total and is the right forgiving
  choice for an easy-button export (>=2 is the only meaningful shape). All
  acceptance criteria met. Closed. Noted the levels-floor-2 for #080 so the
  endpoint surfaces it consistently.
