---
id: 031
title: identity — address (URI), content hash, structure path + sp_render (T15.1-3)
priority: high
size: medium
depends_on: [030]
spec_refs: [build-order.md#T15.1, build-order.md#T15.2, build-order.md#T15.3, how-hrono-works.md, design-sketch-v1.md, app/structuring.py]
---

## Context
Every section and passage from the splitter (#029/#030) needs three identities
before it can be stored, embedded, or recalled: an address (where it came from),
a content hash (what it is, for dedup/embed-once), and a structure path (where it
sits in its file). This ticket builds those three, as pure functions over the
split output + the source metadata. Storage of the pieces and the split job-op
are #032. The precise model is in `how-hrono-works.md`.

## Description
Add an identity module (recommend `src/hrono/ingest/identity.py`):

1. **Address / URI (T15.1)**: assemble a fragment-free URI from FOUR stored
   parts — `source_type`, `instance`, `path`, `version` — rendered as
   `<source_type>://<instance>/<path>@<version>` (git example:
   `git://github.com/acme/webphone/src/ContactService.java@<commit>`). For a git
   source, `instance` is `host/org/repo`, `path` is the repo-relative file path,
   `version` is the commit hash captured by #025. The four parts are the source
   of truth; the URI is RENDERED from them (a rendered column that cannot drift
   from the parts). Position (byte range, ordering) is DATA attached to the
   piece, never part of the identity/URI (fragment-free).

2. **Content hash (T15.2)**: `SHA-256` hex of the piece's raw bytes taken from
   the original file's byte range. Pieces with identical bytes share a hash
   regardless of address — this is the dedup / embed-once key (bodies stored once
   in #032's contents table). Pure function of the byte range's bytes.

3. **Structure path + `sp_render` (T15.3)**: from the packer's structure trail
   (the chain of nodes root->packed-node that #030 attaches to each piece; a
   piece usually has one, several when small siblings share a passage). A segment
   is `{type, name?, idx}` — tree-sitter node type, best-effort display name
   (declaration name / JSON key / markdown heading / XML tag), and the index
   among same-type-same-name siblings from the AST. Synthetic segments are typed
   `~<level>` (e.g. `~line`); byte-chop pieces end in a `raw` segment carrying
   `part`/`of`. `sp_render` renders a path to the compact `sp:` URI:
   percent-encoded names, `.type` for unnamed segments, `[i]` only when idx > 0,
   e.g. `sp:/ContactService/.class_body/getByUser`. Structure paths are unique
   per file by construction.

Mine `app/structuring.py` (`struct_paths`, `sp_render`, `seg`) for the settled
recipe; rewrite clean. All pure, unit-testable with fixtures; no DB, no network.

## Acceptance criteria
- [ ] A git section/passage renders the 4-part URI
      `git://<host>/<org>/<repo>/<path>@<commit>`; the URI is derived from the
      stored parts (changing a part changes the URI; the parts are the source of
      truth) and carries NO byte-range/order fragment.
- [ ] Two pieces with byte-identical content produce the same content hash
      (SHA-256 of the byte range); different bytes produce different hashes; the
      hash is over raw bytes, deterministic.
- [ ] `sp_render` produces the documented form: percent-encoded names, `.type`
      for unnamed segments, `[i]` only when idx > 0; synthetic segments render
      `~<level>`; a byte-chop piece renders its `raw`/`part`/`of` tail.
- [ ] A passage covering several small sibling nodes carries all their structure
      paths; a normal passage carries one; paths are unique per file.
- [ ] Regression-grade tests over fixtures: URI assembly + render, hash
      equality/difference over identical/different byte ranges, sp_render for
      named/unnamed/indexed/synthetic/byte-chop segments, multi-path passage.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Persisting sections/passages/contents or the dedup store (#032 / T15.4).
- The split job-op wiring (#032).
- Embedding (uses the content hash as its key — that is the M2/M3 embed op,
  later).

## Review log
- 2026-08-16 PO: authored as T15.1-3 identity, per how-hrono-works.md. Pure
  functions over #030's split output; consumes the packer's structure trail.
  Address is fragment-free (position is data); content hash is the dedup key;
  sp_render is the settled recipe from structuring.py.

## dev — 2026-08-16

Added `src/hrono/ingest/identity.py` — pure functions over the #029 tree +
#030 pieces + source metadata, no DB/network:
- `Address` (frozen, 4 parts) with `.uri` rendering
  `<source_type>://<instance>/<path>@<version>` — parts are the source of truth,
  URI is derived, fragment-free (position is data on the piece, not identity).
- `content_hash(data)` = SHA-256 hex of the byte range; identical bytes share a
  hash regardless of address (dedup / embed-once key).
- `Segment` + `structure_paths(tree, start, end, part, of)` + `sp_render(path)`.

Design decision (integration): my #030 was implemented byte-only (I deferred
sp-paths to this ticket), so instead of a packer-attached trail, `structure_paths`
RECONSTRUCTS the path from the #029 tree and a piece's byte range — descend while
a single child fully contains the range (a node the packer descended into), then
treat the children falling inside the range as the packed group (one path each;
several for a passage that grouped small siblings). A whole-node passage yields a
single path (whole-node guard); a byte-chop piece appends a `raw` segment with
part/of. This is equivalent to threading a trail and keeps the qa-approved packer
pure. Noted for review in case the team prefers threading through #030 instead.

`sp_render` matches the settled recipe (structuring.py): percent-encoded names
(leading `.`/`~` escaped), `.type` for unnamed segments, `[i]` only when idx > 0,
synthetic segments as `.~<level>`, byte-chop as `.raw[part/of]`. idx counts
preceding same-type-same-name siblings from the tree.

Verified over a real repo file (pack.py): 17 passages, sensible sp-paths
(`sp:/split`, `sp:/Node`, `sp:/.decorated_definition`), 17 distinct content
hashes, correct git URI. Tests: URI assembly + parts-authoritative +
fragment-free; hash sha256/equality-across-position/difference; sp_render for
named/unnamed/indexed/synthetic/raw + percent-encoding + leading-marker escape;
whole-node single path; multi-sibling multi-path; uniqueness per file; byte-chop
raw tail; synthetic path in a no-grammar file. Gate clean: ruff, pytest 329.
Commit 64fe378.

## qa — 2026-08-16

PASS -> po-review. Verified all three identities as pure functions. URI: the
4-part `Address` renders `git://github.com/acme/webphone/src/ContactService.java@
<commit>`, is fragment-free (no `#`/byte-range), and is derived from the parts
(changing a part changes the URI - parts are the source of truth). Content hash:
`content_hash` == `sha256` hex of the byte range, identical bytes share a hash
regardless of position (the dedup/embed-once key), different bytes differ.
`sp_render` produces every documented form - named `sp:/greet`, unnamed
`sp:/.class_body`, indexed `[2]` (omitted at idx 0), synthetic `.~line`,
byte-chop `.raw[k/n]`, percent-encoded names (`%2F`, `%20`), and leading `.`/`~`
escaped (`%2Ehidden`, `%7Eweird`). Drove the reconstruction over real pack.py: 24
passage-paths, all UNIQUE. Confirmed the multi-path branch fires for a passage
covering a SUBSET of siblings (methods m5-m7 of a class body -> `sp:/C/.block/m5`,
`/m6`, `/m7`, three paths), while a whole-node passage yields one; a byte-chop
piece appends a `raw[part/of]` tail; a real-sized no-grammar file yields synthetic
`.~<level>` segments. The design decision to RECONSTRUCT structure paths from the
#029 tree + a piece's byte range (rather than threading a trail through #030 -
which dev kept byte-only and flagged for review) is a sound equivalent: it
correctly descends into packer-descended nodes and groups the children inside the
range, and it keeps the packer pure. Two cosmetic, non-blocking observations (no
AC broken, paths still valid + unique): a whole-file no-grammar passage renders
`sp:/` (the root, no segments - a valid degenerate), and the byte-chop parts of
the `var x=<huge>;` shape have slightly inconsistent path depth because #030's
balloon-fix chops the prefix+atomic together (part 1 = variable_declaration/raw,
part 2 = identifier/raw) - each still a unique, correctly-marked `raw[k/n]` tail.
Tests are regression-grade (URI assembly + fragment-free + parts-authoritative;
hash sha256/equality-across-position/difference; sp_render named/unnamed/indexed/
synthetic/raw/percent-encode/leading-marker; whole-node single path; multi-sibling
multi-path; per-file uniqueness; byte-chop raw tail; no-grammar synthetic). Code
review clean: frozen Address/Segment, pure functions, typed, docstrings only, no
emojis; correct layering (identity depends on split). Tree was clean, 031
committed in isolation. Commit 64fe378 is a proper atomic Conventional Commit.
Re-ran the gate: ruff format clean (116 files), ruff check passed, pytest 329
passed.
- 2026-08-16 PO: PASS -> done. Verified all three identities as pure functions.
  URI: the 4-part Address renders git://<host>/<org>/<repo>/<path>@<commit>,
  fragment-free (no #/byte-range), parts-authoritative (changing a part changes
  the URI). content_hash == SHA-256 hex of the byte range; identical bytes share
  a hash regardless of position (dedup/embed-once key), different bytes differ.
  sp_render produces valid unique sp:/... paths across every form (named,
  unnamed `.type`, synthetic `.~blank-line`, indexed `[i]`); over identity.py all
  25 paths are unique and sp:-prefixed. Design note: dev kept #030's packer
  byte-only and structure_paths RECONSTRUCTS paths from the #029 tree + a piece's
  byte range (rather than threading a trail) - a sound equivalent that keeps the
  packer pure; ACs are behavioral and met. Two cosmetic non-blocking items
  (whole-file no-grammar -> `sp:/` root; byte-chop part depth from #030's
  balloon-fix) break no AC (paths valid + unique). Tree clean, 031 committed in
  isolation. Ran the gate: ruff format (116 clean), ruff check clean, pytest 329
  passed. Fully unblocks #032 (the last M2 ticket). Closed at 64fe378.
