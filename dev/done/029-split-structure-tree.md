---
id: 029
title: split — tree-sitter structure tree + synthetic delimiter cascade (T14.1+T14.2)
priority: high
size: big
depends_on: []
spec_refs: [build-order.md#T14.1, build-order.md#T14.2, design-sketch-v1.md, app/structuring.py, app/structuring.toml]
---

## Context
The splitter turns a file's raw bytes into a structure tree that the packer
(#030) then packs into sections and passages. This is the technical core of
ingest: chunking that respects code/document structure instead of cutting
through functions and JSON. The settled recipe is the prototype's
`structuring.py` (structure-aware, cAST-style) — mine it for the recipe but
rewrite clean per CLAUDE.md; do not port the prototype's structure. This ticket
builds the structure-tree half (T14.1 parse + T14.2 synthetic cascade); the
packer + edge cases are #030. Load `engineering:developer`.

## Description
Add a splitter package (recommend `src/hrono/ingest/split/`). Two pieces:

1. **Tree-sitter parse + grammar-by-extension (T14.1)**: resolve a tree-sitter
   grammar from the file extension (via `tree-sitter-language-pack` per the
   stack) and parse raw bytes into a parser structure tree. A file with no
   grammar (unknown extension, plain text/data) yields a single top span the
   cascade then structures. Expose best-effort `node_type` and `node_name`
   (display name per grammar family, e.g. a function/class name) used later for
   the sp-path (#031). Parsing is over bytes, and all offsets are BYTE offsets
   (never char) so reassembly is exact.

2. **Synthetic delimiter cascade (T14.2)**: for spans the parser gives no useful
   children for (structureless text, or a span larger than the passage budget
   with no grammar), grow the tree with synthetic nodes by a fixed delimiter
   cascade, in order — `"\n\n"` (blank-line), `"\n"` (line), `". "` (sentence),
   `","` (comma), `" "` (word) — deepening a level only while a span still
   exceeds the passage budget (800 B). A cascade level that produces FEWER THAN
   TWO pieces is skipped in favor of the next level (no pointless single-child
   deepening). The cascade is data (a list), walked by one routine, not an
   if/elif ladder. Synthetic nodes carry a type recording the level (`~<level>`,
   e.g. `~line`) so the packer and sp-path (#031) treat them uniformly with
   parsed nodes.

The result is a single structure tree of byte spans (parsed nodes + synthetic
delimiter nodes) covering the whole file with no gaps or overlaps — the input to
#030. Keep budgets/cascade in one config-or-constants module matching the settled
recipe (`paragraph_bytes=800`, cascade above); the packer budgets land with #030.
Pure function of (path, bytes) so it is unit-testable with fixture files, no
network, no DB.

## Acceptance criteria
- [ ] A source file with a supported grammar (e.g. Python) parses into a
      structure tree whose spans are byte ranges covering the file with no
      gaps/overlaps; `node_name` returns a sensible display name for named
      constructs (function/class).
- [ ] A file with no grammar (plain text / unknown extension) still yields a
      structure tree via the synthetic cascade.
- [ ] The delimiter cascade deepens in the documented order and only while a span
      exceeds the passage budget; the cascade is expressed as data, walked by one
      routine.
- [ ] All offsets are byte offsets; concatenating the leaf spans in order
      reproduces the original file bytes exactly (no gaps/overlaps) — asserted by
      a test.
- [ ] Unknown/binary-ish content does not crash the parser path (it falls through
      to the cascade); grammar resolution is by extension via the language pack.
- [ ] Regression-grade tests over fixture files: a code file (named-node
      structure), a prose/markdown file (cascade structure), a no-grammar file,
      and the exact-cover (no gap/overlap) property.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The greedy two-budget packer (sections 10 KB / passages 800 B) and edge cases
  (byte-chop, sub-64 merge, min-group flush) — that is #030.
- sp-path extraction / `sp_render` / URIs / content hash — T15 (#031).
- Persisting anything / the split job-op wiring — T15 storage (#032) + jobs.

## Review log
- 2026-08-16 PO: authored as the structure-tree half of T14. Recipe is settled
  in the prototype `structuring.py` (`parser_for`/`deepen`); rewrite clean.
  Byte-offset exactness is called out because #032's byte-identical reassembly
  depends on it. Sized `big` (tree-sitter integration + the cascade); split
  parse-vs-cascade into two commits if a clean seam exists.

## dev — 2026-08-16

Built the structure-tree half of the splitter as a clean package
`src/hrono/ingest/split/` (mined the prototype recipe, rewrote per CLAUDE.md).
Layers, bottom-up: constants (PARAGRAPH_BYTES=800 + the CASCADE data) <- node
(immutable byte-span `Node`) <- cascade (`deepen`) / grammar (`parser_for`) <-
tree (`structure`). Public: `from hrono.ingest.split import structure, Node`.

Design decisions:
- Exact cover is a property of THIS tree (029 asserts it), not deferred to the
  packer: `_convert` tiles each parent by using next-sibling-start as the child
  boundary, so inter-token whitespace folds into the preceding sibling and
  leading bytes into the first child. tree-sitter's own children leave gaps
  (the `def foo\n\nclass Bar\n` case has a 2-byte gap + tail); tiling closes
  them. Root is always [0, len(raw)); leaves tile the file.
- Cascade keeps the delimiter with the preceding piece (`_split`) so pieces
  tile exactly; a level yielding <2 pieces recurses to the next level; a piece
  recurses only while > PARAGRAPH_BYTES. Cascade is data (tuple of Delimiter),
  walked by one routine. Synthetic nodes typed `~<level>` (e.g. `~line`).
- No-grammar file -> root type "text" with cascade children. Unknown/binary
  content never crashes: unknown ext -> no parser -> cascade; a known ext over
  binary bytes parses fine (tree-sitter tolerates arbitrary bytes).
- All offsets are byte offsets; `node_name` best-effort per family (name/key
  fields, markdown heading, xml tag) baked onto Node.name; `node_type` is
  Node.type.

Deps added (pinned, lockfile committed): tree-sitter 0.25.2,
tree-sitter-language-pack 0.11.0.

Verified against the real binary path is N/A (pure library; the split job-op is
#032) — instead drove `structure` over real repo files: engine.py (module,
1181 leaves, named imports/defs), README.md (document, section "hrono"),
pyproject.toml (document) — all reassemble byte-for-byte. Fixture tests cover
code named-node structure, markdown grammar, no-grammar cascade, cascade order
+ skip-<2 + only-over-budget, no-delimiter single leaf, binary/empty/tiny, and
the exact-cover property parametrized over 8 inputs.

Out of scope (left for their tickets): the greedy two-budget packer + byte-chop
+ tiny-merge (#030), sp-path/URIs/hash (#031), storage + job-op wiring (#032).

Gate clean: ruff format/check, pytest 283 passed. Commit c31c155. Built
parse+cascade as one package (tree depends on cascade, so no clean two-commit
seam).

## qa — 2026-08-16

PASS -> po-review. Verified all dimensions (engineering:developer lens on the
splitter). The load-bearing invariant - leaves tile the file byte-for-byte with
no gaps/overlaps - is implemented correctly: `_convert` forces every node to
cover its ASSIGNED span and tiles children via `_bounds`
(`edges=[start, kids[1:].start_byte..., end]`), so leading bytes fold into the
first child, inter-node bytes into the preceding sibling, and trailing bytes into
the last child; `cascade._split` keeps each delimiter with its preceding piece so
pieces tile exactly. Hammered exact-cover + byte-identical reassembly over 134
inputs: all 123 real repo source files (py/md/toml/...) PLUS 11 adversarial
cases - empty, 1-byte, no-trailing-newline, leading whitespace, trailing bytes
after the last node, unicode, the `def foo\n\n\nclass Bar` gap case, a no-grammar
file, a 2000B single line, arbitrary binary bytes under a `.py` extension, and
CRLF - every one tiles exactly and reassembles to the original bytes. Cascade
verified data-driven (the `CASCADE` tuple walked by one `deepen` routine):
deepens in the documented order, skips a level yielding <2 pieces (2000B line ->
falls through blank-line/line/sentence/comma to `~word`), and only recurses into
pieces over PARAGRAPH_BYTES=800. Grammar-by-extension via the language pack; an
unknown extension or arbitrary binary content never crashes (falls through to the
cascade / tree-sitter tolerates bytes). `node_name` resolves named constructs
(function `greet`, class `Widget`, markdown headings, xml tags). All offsets are
byte offsets. Tests are regression-grade (parametrized exact-cover over 8 inputs +
named-node/markdown/no-grammar/cascade-order/skip-<2/only-over-budget/
single-leaf/data-driven-cascade). Deps tree-sitter + tree-sitter-language-pack
added with ranges in pyproject and exact pins in the committed uv.lock (project
convention). Commit c31c155 is a proper atomic Conventional Commit (`feat:`),
no emojis; the split package is self-contained under `src/hrono/ingest/split/`.

Verified the gate on 029 IN ISOLATION: the working tree carried unrelated
uncommitted #033 WIP (`src/hrono/admin/`, `tests/admin/`, and edits to
`auth/users.py`/`cli.py`), so I stashed it, re-ran the gate on the clean 029
commit (ruff format/check clean, pytest 283 passed), and restored the WIP - 029
neither touches those files nor imports them, so it stands alone. Process note
(not a 029 defect): a ticket should be committed and the working tree left clean
before it enters verifying - leaving the next ticket's WIP in the tree risks
conflating a clean gate run across tickets. Flagging for hygiene; 029's committed
deliverable is clean and independently verified.
- 2026-08-16 PO: PASS -> done. Verified the load-bearing invariant myself: leaves
  tile the file byte-for-byte with no gaps/overlaps and reassemble to the
  original bytes. 029's own 18 tests pass; independently drove `structure` over
  real files (tree.py 530 leaves, pyproject.toml 160, README.md 28) + 8
  adversarial inputs (empty, 1-byte, no-trailing-newline, leading whitespace,
  2000B single line, arbitrary binary under .py, CRLF, the def/blank/class gap) -
  every one exact-cover=True and reassemble=True. Cascade is data-driven (CASCADE
  tuple, one deepen routine, deepen order + skip-<2 + only-over-budget), grammar
  by extension via the language pack, no crash on binary/unknown, byte offsets
  throughout, node_name resolves named constructs. This tiling exactness is what
  #032's storage reassembly relies on. Verified 029 in ISOLATION (the tree
  carried uncommitted #033 WIP, which 029 neither touches nor imports). Gate on
  the clean 029 commit: ruff format/check clean, pytest 283 passed. Unblocks
  #030 (packer). Closed at c31c155.
