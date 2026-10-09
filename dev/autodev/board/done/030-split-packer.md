---
id: 030
title: split — greedy two-budget packer + edge cases (T14.3+T14.4)
priority: high
size: big
depends_on: [029]
spec_refs: [build-order.md#T14.3, build-order.md#T14.4, app/structuring.py, app/structuring.toml]
---

## Context
With the structure tree from #029, the packer turns it into the two leaf
granularities hrono stores: **sections** (~10 KB, the clustering/traversal unit)
and **passages** (~800 B, the recall-injection unit), where a section reassembles
byte-identically from its passages. This is the same greedy whole-node mechanism
run at two budgets. This ticket adds the packer (T14.3) and the edge cases that
keep it well-behaved (T14.4). Settled recipe: prototype `structuring.py`
(`pack`, `split_file`, `split_file_hier`, `merge_tiny`); rewrite clean.

## Description
Add the packer on top of #029's structure tree, producing sections each holding
its ordered passages.

1. **Greedy whole-node packer, two budgets (T14.3)**: walk the structure tree and
   greedily fill spans up to a byte budget, keeping whole structural nodes
   together. Run it at the passage budget (`800 B`) to make passages and at the
   section budget to make sections; a section's passages are exactly the passages
   whose byte ranges fall in it (nesting, not a second independent split), so a
   section == the concatenation of its passages, byte-identical.
   - **Section budget is category-based** (per how-hrono-works.md): an
     extension -> category table maps every file to `code`, `docs`, or `data`
     with section budgets **code 10 KB / docs 10 KB / data 2 KB** (each the
     log-scale Kneedle knee measured over four large repos). This is data (an
     ext->category->budget table), not a flat constant.
   - The passage pack runs INSIDE each section's node group, with the
     `min_group` rule (`100`): a structural group that reaches `min_group` is
     flushed and stands alone at its boundary rather than being greedily merged
     with unrelated neighbors; below that, grouping only rescues small spans.
   Budgets/min_group/category-table are the settled constants (data, not
   scattered literals).
- [Terminology] production `passage` == prototype `paragraph`; production
  `section` == prototype `chunk`. Keep the production names.

2. **Edge cases (T14.4)**:
   - **byte-chop**: a single atomic span larger than the budget (e.g. a
     minified line, a huge string) with no further structure is chopped at byte
     boundaries into budget-sized pieces, each marked as a raw part
     (`part k of n`) so #031 can render its `raw`/`part`/`of` sp-path tail.
   - **sub-64 merge (`min_para=64`)**: structural crumbs smaller than `min_para`
     merge into the preceding passage (a leading crumb merges into the next),
     keeping the struct path of the kept passage — no orphan micro-passages.
   - **min-group flush**: flush a sibling group once it reaches `min_group` at the
     structural boundary (from the packer above).

The output is an ordered list of sections, each with its ordered passages; every
passage carries its byte range (start,end) into the original file. Pure function
of the #029 structure tree + raw bytes; unit-testable with fixtures, no DB.

## Acceptance criteria
- [ ] Packing produces sections at the file's category budget (code/docs 10 KB,
      data 2 KB) and passages ~<=800 B (budgets are hard maxima except where a
      single atomic span forces byte-chop); each section's passages concatenate
      byte-identically to the section's bytes, and the sections concatenate to
      the whole file.
- [ ] A structural node group reaching `min_group` stands alone at its boundary;
      smaller spans are greedily packed — verified on a fixture with mixed group
      sizes.
- [ ] byte-chop: an atomic span far over budget is split into byte-budget pieces
      with no data lost and exact reassembly.
- [ ] sub-64 merge: crumbs under `min_para` merge into the adjacent passage (no
      passage smaller than `min_para` survives except a whole tiny file); the
      kept passage's struct trail is preserved.
- [ ] Budgets and `min_para`/`min_group` are the settled constants expressed as
      data; the packer walks the tree, no per-node-type branch ladder.
- [ ] Byte-identical reassembly holds across all fixtures: code, prose, a
      minified/oversize line, a tiny file, and a file with many small structural
      crumbs.
- [ ] Regression-grade tests assert the reassembly property, the two budgets,
      min_group standalone, byte-chop, and sub-64 merge; a test fails if
      reassembly ever loses/reorders a byte.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Assigning URIs / sp-paths / content hashes to the sections/passages (T15
  #031) — output is in-memory sections/passages with byte ranges only.
- Persisting to the DB / byte-identical reassembly FROM storage (T15 #032) —
  this ticket proves reassembly from the in-memory split; storage reassembly is
  #032.
- The split job-op wiring (runs the splitter over synced+filtered files as a
  job) — lands with storage #032 + jobs.

## Review log
- 2026-08-16 PO: authored as the packer half of T14. Two budgets from the
  settled recipe (passage 800 B / section 10 KB), min_para 64 / min_group 100.
  Byte-identical section<->passages nesting is the load-bearing invariant #032's
  storage reassembly relies on. Sized `big`; packer-vs-edge-cases can split into
  two commits.

## dev — 2026-08-16

Added the greedy two-budget packer on top of #029's structure tree, in the same
`src/hrono/ingest/split/` package: `section.py` (frozen `Section`/`Passage`
byte-span models) + `pack.py` (the packer) + category budgets in `constants.py`.
Public: `from hrono.ingest.split import split, Section, Passage`;
`split(path, raw) -> tuple[Section, ...]`.

Key simplification vs the prototype: because #029 tiles every parent exactly
(sibling ends meet, no gaps), the prototype's "trailing gap rides along" hack is
unnecessary — `nxt_start == child.end` always, so one greedy `_pack` gives
gap-free coverage by construction. Struct-path/trail/seg machinery is dropped
entirely (that is #031); the packer is pure offset math on the tree.

Mechanism (one routine, `_pack`, run at two budgets, no per-node-type ladder):
consecutive whole nodes accumulate while they fit; a node over budget is
descended into; a childless atomic span is byte-chopped (`_chop`) into
budget-sized raw parts marked `part k of n`; a sibling group reaching MIN_GROUP
(100) flushes and stands alone at its boundary. Sections come from `_pack` at the
file's category budget; passages come from `_pack` at PASSAGE_BYTES (800) with
min_group=100 INSIDE each section's node group (single-node sections descend to
that node's children), so passages nest inside sections by construction and a
section == the byte-identical concat of its passages. `_merge_tiny` folds
sub-MIN_PARA (64) crumbs into a neighbour (leading crumb merges forward),
combining node groups so a merged span still tiles. `_stretch` forces a section's
first/last passage to the section bounds, closing any group/merge boundary
discrepancy so passages always cover the section exactly.

Settled constants as data: PASSAGE_BYTES 800, MIN_PARA 64, MIN_GROUP 100, and an
ext -> category -> section-budget table (code/docs 10240, data 2048; default
docs) taken verbatim from the prototype `chunking.toml`. Renamed the #029
constant PARAGRAPH_BYTES -> PASSAGE_BYTES for production naming (updated cascade,
tree, and the #029 test).

Verified (pure library; the split job-op is #032) by packing real repo files:
pack.py (code, 1 sec / 16 pass, max_pass 757), README.md (docs), pyproject.toml
(data, 2 KB budget), and uv.lock (89 KB -> 11 sections each <= 10116, 261
passages <= 775) — all reassemble byte-identically with correct per-section
nesting. Fixture tests assert the reassembly property (6 inputs), the two
category budgets, min_group standalone (funcs stand alone / tiny stmts group),
byte-chop (1..n of n markers, exact reassembly), ordinary-passages-have-no-
markers, sub-64 crumb merge, empty file, and tiny file.

Out of scope, left for their tickets: URIs/sp-paths/content hashes (#031),
DB persistence + reassembly-from-storage (#032), the split job-op wiring (#032).

Built packer + edge cases as one commit (byte-chop/merge live in the same
packer; no clean two-commit seam). Gate clean: ruff format/check, pytest 303
passed. Commit 87c7df9.

## qa — 2026-08-16

FAIL -> back to todo. One blocking defect on the byte-chop / passage-budget AC
("byte-chop: an atomic span far over budget is split into byte-budget pieces" and
"passages ~<=800 B ... except where a single atomic span forces byte-chop").

Finding (a byte-chopped over-budget atomic span adjacent to sub-MIN_PARA crumbs
yields an oversize, UN-chopped passage):
`split(Path("m.js"), b"var x=" + b"a"*30000 + b";")` produces section [0,10246)
containing a SINGLE passage [0,10246) of 10246 bytes - 12.8x the 800 B budget -
with `part=None, of=None` (i.e. not a legitimate byte-chop part). Reassembly is
still byte-identical (no data loss), so this is a granularity / budget-violation
+ missing part/of defect, not corruption.

Root cause (pack.py): `_chop` returns `_Span`s with `nodes=()`. tree-sitter gives
`var x=<30000 a's>;` as tiny nodes (`var`/`x`/`=`/`;`) plus one 30000 B atomic
identifier. At the section pass the atomic node is byte-chopped into 10240 B
`_Span`s (nodes empty); `_merge_tiny` then folds the tiny `var/x/=` crumbs into
the first chop-span (and the trailing `;`), so section 0's `.nodes` cover only
`[0,6)` while its span is `[0,10246)`. In `_passages`, `_group(section)` returns
those crumb nodes (covering the 6-byte prefix only), `_pack` packs them into one
small span, and `_stretch` extends that span's END to `section.end` - ballooning
a single passage to the full 10246 B section, un-chopped. The byte-chop structure
of the atomic content is lost between the section and passage passes whenever a
crumb-merge touches a chop-span.

Why the tests miss it: the byte-chop fixture in test_pack.py uses a bare atomic
over-budget span with no adjacent sub-MIN_PARA crumb, so the chop parts survive;
the crumb-merge-vs-chop interaction (the realistic `var x=<huge>;` /
`const y = "<huge>";` minified shape the ticket explicitly targets) is untested.

Required change: the passage pass must guarantee every passage <= PASSAGE_BYTES,
byte-chopping any span that exceeds it regardless of node coverage. Options: (a)
have `_passages`/`_stretch` re-`_chop` any resulting passage span longer than
PASSAGE_BYTES into part/of-marked parts; (b) preserve byte-chop parts through
`_merge_tiny` (don't let a chop-span's parts be collapsed into a crumb); or (c)
in `_passages`, byte-chop any `[section]` range not covered by the wrapper's
child nodes. Add a regression test: a byte-chopped atomic span PRECEDED and
FOLLOWED by tiny crumbs asserts NO passage exceeds PASSAGE_BYTES and that the
over-budget atomic content is split into part/of-marked passages - it must fail
on the current code.

Everything else verified and sound (do not re-litigate on return): two-level
byte-identical reassembly (sections->file AND passages->section) holds over 132
real repo files plus adversarial inputs (empty, tiny, code, prose, data,
crumbs, a pure oversize word); section category budgets honored (code/docs
10240, data 2048, 0 sections over budget); sub-64 crumb merge (no non-chop
passage under MIN_PARA in a large file); min_group standalone; constants-as-data
(PASSAGE_BYTES/MIN_PARA/MIN_GROUP + ext->category->budget table), packer walks
the tree with no per-node-type ladder; and the #029 PARAGRAPH_BYTES->
PASSAGE_BYTES rename did not break #029's exact-cover (re-verified). Gate: pytest
303 passed and ruff clean on the committed code (an earlier transient "1 file
would reformat" was unrelated in-tree WIP - now clean). The fix should keep the
reassembly property and add the crumb+chop test.

## dev (re-fix after qa bounce) — 2026-08-16

qa was right: `_stretch` + the final `_pack` `flush(node.end)` could balloon one
passage to the whole section when a crumb-merge folded a byte-chop span's parts
away, so a section's `.nodes` under-covered its span and the byte-chop was lost
between the section and passage passes (the `var x=<huge>;` minified shape).

Fix (qa option a): added `_enforce_budget` as the final step of the passage pass
(`_pack` -> `_stretch` -> `_merge_tiny` -> `_enforce_budget`). It byte-chops any
resulting passage still over PASSAGE_BYTES into `part`/`of`-marked pieces
regardless of node coverage, guaranteeing every passage <= 800 B. Reordered so
merge runs before the budget enforcement, so ordinary crumbs still merge while
the enforcement is the last word on size.

Regression test added (`test_byte_chop_survives_crumbs_flanking_an_atomic_span`):
`var x=<30 KB>;` asserts NO passage exceeds PASSAGE_BYTES, the atomic content is
split into part/of-marked passages, and section+file reassembly stays exact — it
fails on the pre-fix code (one ~10 KB passage). Verified the fix on all three qa
adversarial shapes (`var x=<30k>;`, `const y="<30k>";`, crumb-blob-crumb): 0
over-budget passages, marked, exact reassembly; real files unchanged
(pack.py max passage 794, uv.lock 775). Gate clean: ruff, pytest 318 passed.
Commit b22bc7f.

## qa — 2026-08-16 (re-review)

PASS -> po-review. The blocking byte-chop / passage-budget defect is fixed. Dev
took qa option (a): `_passages` now runs `_pack -> _stretch -> _merge_tiny ->
_enforce_budget`, and the new `_enforce_budget` byte-chops any span still over
PASSAGE_BYTES into `part`/`of`-marked pieces regardless of node coverage - so a
crumb-merged byte-chop can no longer balloon a passage, and merge still runs
before enforcement so ordinary crumbs fold. Re-ran the exact kickback repro plus
the two other adversarial shapes: `var x=<30 KB>;`, `const y="<30 KB>";`, and
crumb-blob-crumb all now yield ZERO over-budget passages (max passage = 800,
the atomic content split into part/of-marked passages) with exact section+file
reassembly - the pre-fix ~10 KB passage is gone. Regression across 132 real repo
files: two-level byte-identical reassembly (sections->file AND passages->section)
still holds and the max passage across every file is 794 (<= 800), so normal
files are unaffected. The new `test_byte_chop_survives_crumbs_flanking_an_atomic_
span` locks it in (fails on the pre-fix code). All previously-verified properties
(category budgets, sub-64 merge, min_group, constants-as-data, #029 exact-cover)
still hold. Tree was clean and 030 committed in isolation this time. Commit
b22bc7f is a proper atomic Conventional Commit (`fix:`). Re-ran the gate: ruff
format clean (114 files), ruff check passed, pytest 318 passed.
- 2026-08-16 PO: PASS -> done. This ticket earned a precise qa bounce: a
  byte-chopped over-budget atomic span flanked by sub-MIN_PARA crumbs (the
  minified `var x=<30 KB>;` shape the ticket targets) ballooned into one ~10 KB
  un-chopped passage, violating the 800 B passage budget - fixed by adding
  `_enforce_budget` as the final passage-pass step (byte-chops any over-budget
  span into part/of pieces regardless of node coverage), with merge running
  before enforcement. Independently drove `split` over real files and the three
  adversarial shapes: two-level byte-identical reassembly (sections->file AND
  passages->section) holds everywhere (uv.lock 89 KB -> 11 sections all
  reassemble, max passage 775), and `var x=<30k>;` / `const y="<30k>";` /
  crumb-blob-crumb all yield ZERO over-budget passages (max 800, atomic content
  byte-chopped) with exact reassembly. Category budgets honored (data 2 KB /
  code+docs 10 KB), min_group standalone, sub-64 crumb merge, constants-as-data,
  one packer walks the tree (no per-node ladder). Tree clean, 030 committed in
  isolation. Ran the gate: ruff format (114 clean), ruff check clean, pytest 318
  passed. Completes T14 split (029 structure tree + 030 packer). Unblocks #031.
  Closed at b22bc7f.
