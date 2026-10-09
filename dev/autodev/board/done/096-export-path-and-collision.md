---
id: 096
title: Export — absolute paths break `tree export`, and parentless nodes collide onto one brief path
priority: high
size: medium
depends_on: []
spec_refs: [build-order.md#T30, build-order.md#T31, build-order.md#T32]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F19, F20
---

## Context
`export/render.py:42-48` special-cases the ROOT's own brief to `"root.md"` but
not the root's sections, and `_directory` returns `""` for any parentless node.

## Description
**F19 — `hrono tree export` writes zero files.** 93 of 94 manifest paths come
back with a leading slash (`.e2e/artifacts/export-manifest.txt`):

```
   1621B  /benchmark-js-97.md
   4570B  /brief.md
   1489B  root.md            <- the only relative one
```

`_materialize` does `out / entry["path"]`, and pathlib discards the left side of
a join with an absolute path, so the (correct) traversal guard refuses the first
entry and the command aborts:

```
$ hrono tree export default -o exports/attempt1   ->  exit 1
refused to write outside exports/attempt1: '/benchmark-js-97.md'
$ find exports/attempt1 -type f | wc -l
0
```

**F20 — briefs are silently dropped.** With several parentless nodes,
`_directory` is `""` for all of them, so `f"{directory}/brief.md"` is the same
dict key for every one. Six of seven briefs were overwritten; the manifest
contained one `/brief.md` and the other five briefs (chalk source,
itsdangerous docs, itsdangerous source, project config, licences) were absent
with no error. `export/store.py:load` also picks the root with
`max(node_level, key=...)`, i.e. an arbitrary node when levels tie — so
`root.md` presented one repo's brief as the summary of a three-repo map.

Same collision class as the fix in 95394ce, reintroduced by the empty-directory
case.

Work:
- The renderer must never emit an absolute path.
- Every node needs a distinct path, including top-level ones.
- `_materialize` should normalise/reject a leading slash rather than let pathlib
  reroot it, and should report how many files it refused.
- `export/store.py:load` should refuse a forest (or name each root) rather than
  pick one silently.

## Decision (2026-09-12, dev — technical call, no PO input needed)

Technical half, decided:
- the renderer never emits an absolute path — the root's sections are written
  relative, exactly like every other node's;
- every node gets a distinct directory name, parentless ones included, so two
  briefs can never collide onto one key;
- `_materialize` normalises (or refuses) a leading slash instead of letting
  pathlib reroot it, and reports how many entries it refused.

## Resolved 2026-09-12 (PO)

No product call needed: `_collect_root` already guarantees exactly one root
whenever recursion stops, so a forest is never a legitimate stored state — it
only appeared here because 094's crash aborted `build_tree` before
`_collect_root` ran. `export/store.py:load` should therefore treat >1 top-level
node as a **defect**, not a shape to render: fail loudly (a 5xx-worthy internal
error, or a clear "tree is not built to a single root") rather than silently
picking one node with `max(node_level, ...)` and dropping the others' briefs.

## Acceptance criteria
- [ ] Every manifest path is relative; `hrono tree export` writes all of them.
- [ ] A tree with N parentless nodes exports N distinct briefs, or the endpoint
      fails with a clear "not built to a single root".
- [ ] Regression test asserting no path in the manifest starts with `/` and that
      brief paths are unique.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 dev: started; moved to in-progress.
- 2026-09-14 dev: implemented and committed as `823b796`. Both halves of the
  Decision block plus the PO's resolution.

  **F19 — the renderer can no longer emit an absolute path.**
  `export/render.py`: new `_under(directory, name)` joins under a directory and
  stays RELATIVE when the directory is `""`, and `_directory` now walks from the
  node UP TO THE ROOT (root excluded) instead of walking while a parent exists.
  Only the root is `""`, so its own sections land beside `root.md` at the top of
  the export instead of at `/<name>.md`. Nothing changes for a well-formed tree:
  a child of the root is still `<name>-<id>/`, a grandchild still nests.

  **F20 — a forest is a defect, not a shape (PO's resolution).**
  `export/store.py:_root` replaces `max(node_level, key=...)`: exactly one node
  at the top level, else `Internal` (new 500 subclass in `errors.py`, code
  `internal-error`) with message "tree is not built to a single root: N nodes at
  its top level" and `details` carrying the tree, the level and the node ids.
  The renderer is ALSO made total for that case rather than relying on the
  loader: a parentless non-root node now gets its own id-suffixed directory, so
  two briefs can never collide onto one key even if a forest reaches `render`.
  **Deliberately NOT refused: an unparented leaf BELOW the top level** — that is
  #114 (a leaf the incubator drained in after the build), and it is one node at
  the top level, not a forest. Refusing it would turn #114's partial
  invisibility into a total export outage; test
  `test_an_unparented_leaf_below_the_root_still_loads` pins that split.

  **`_materialize` normalises, counts, and no longer loses the whole export.**
  `tree/commands.py`: the payload path is `lstrip("/")`-ed BEFORE the join, so a
  server-side leading slash means "top of the export" rather than letting
  pathlib reroot it; the traversal guard is unchanged for genuine escapes, but a
  refused entry is now collected and skipped instead of aborting the run —
  one hostile entry costs its own file, not the other 93. The command prints
  "Wrote N file(s)" (pluralised) and then exits 1 with "refused N of M files
  that would write outside <out>: ..." if anything was refused.

  Tests (12 new, 659 total), each verified regression-grade by mutating the
  source in place and watching the matching test go red:
  - `_under` reverted to always prefixing ->
    `test_the_roots_own_sections_render_beside_root_md` and
    `test_a_root_carrying_sections_serves_relative_paths` fail;
  - `_directory` reverted to the old parent-walk ->
    `test_a_parentless_node_keeps_its_own_brief_path` fails (both briefs
    collapse onto one key, exactly F20);
  - `_root` reverted to `max(node_level, ...)` -> `test_a_forest_is_a_loud_
    defect` and `test_a_tree_that_is_not_built_to_one_root_fails_loudly` fail;
  - the `lstrip("/")` removed -> `test_export_normalises_a_server_absolute_
    path` fails;
  - the refusal collected-and-skipped reverted to raise-on-first ->
    `test_a_refused_entry_does_not_cost_the_whole_export` fails.
  Also `test_no_rendered_path_is_absolute` and
  `test_every_manifest_path_is_relative` as broad invariants, and
  `test_an_empty_tree_is_still_none` for the unbuilt case.

  **Real end-to-end verification on a COPY of `.e2e/run/.hrono/hrono.db`**
  (`.e2e/` never touched — copied to scratch, server run from scratch):
  the stored database IS F20's state (7 nodes, all level 0, 0 `node_children`,
  7 briefs). `hrono serve` on the copy applied 0021/0022, and:
  - `GET /trees/default/export` -> **500** `{"code":"internal-error",
    "message":"tree is not built to a single root: 7 nodes at its top level",
    "details":{"tree":"default","level":0,"nodes":[1,2,4,5,8,9,10]}}`, and
    `hrono tree export default -o exports/forest` -> exit 1, that one line on
    stderr, 0 files. Before this commit the same call returned 200 with a single
    `/brief.md` and six briefs silently gone.
  - Then, to drive F19 itself, a level-1 root over the real 7 topics (via
    `cluster_store.replace_level` + a `briefs.upsert`, no LLM) and a restart:
    `hrono tree export default -o exports/attempt1` -> exit 0,
    **"Wrote 102 files to exports/attempt1."**, `find -type f` = **102** on
    disk, the 7 `brief.md` files in 7 DISTINCT directories, `root.md` with its
    mechanical child links, section files carrying their `git://` URI header,
    0 files written outside the output directory. The manifest itself: 102
    entries, **0 absolute paths, 0 duplicate keys, 7 briefs**. The original run
    wrote 0 files and exited 1 on this exact command.

  Out of scope, left alone: #114 (the unparented drained leaf), #102's
  `brief_upper.py:101` raw "Children:" list, and the brief-quality findings
  (F21/F23) that make some link titles a whole paragraph.
  Gate clean: `ruff format` (222 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **659 passed**. Handing off to verifying.
- 2026-09-14 qa: **FAIL — back to todo.** Both headline defects are genuinely
  fixed and I reproduced every claim independently. One blocking finding, in
  `_materialize`, found by probing the guard this ticket rewrote.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `823b796`: `ruff format --check` 222 files unchanged,
    `ruff check` clean, `pytest` **659 passed** in 37.0s.
  - **The traversal guard still holds — the `lstrip("/")` did not weaken it.**
    Driven against a real filesystem with a canary directory, which stayed
    empty throughout. Refused: `'/../../etc/passwd'`, `'../escape.md'`,
    `'a/../../escape.md'`, `'////../../../CANARY/pwned.md'`, `'..'`.
    Normalised safely into the export: `'/etc/passwd'` -> `out/etc/passwd`,
    `'//etc/passwd'` -> `out/etc/passwd`, `'/leading-slash.md'`,
    `'a/b/../c.md'` -> `out/a/c.md`. No URL-decoding layer exists, so
    `'..%2f..%2fetc%2fpasswd'` is a literal filename, not an escape.
    **Symlinks handled**: an output directory that IS a symlink works
    correctly; a PRE-EXISTING symlink subdir inside `out` pointing at another
    directory is refused (`'sub/leak.md'` -> refused, target dir untouched), as
    is `'/etc/passwd'` when `out/etc` is a symlink outward — `.resolve()` on
    both base and target is doing the right work, and the lstrip runs BEFORE
    resolution so anything still normalising outside is caught.
  - **The renderer cannot emit a separator at all.** `render.py:161` `_slug`
    maps everything outside `[a-z0-9]` to `-`, so no brief heading or section
    path can inject `/` or `..` into a key. The guard is defence in depth, as
    intended.
  - **No regression for a well-formed tree — byte-identical.** I rendered the
    same rooted copy of the real corpus under `18bb2b2` and under `823b796` (a
    worktree with `PYTHONPATH` asserted inside it) and diffed the full
    path -> content maps: 102 keys each, `identical: True`, no key added, none
    removed, no content changed.
  - **Deep trees nest correctly** — not just the 2-level real corpus. A
    synthetic 3-stored-level tree (4 leaves -> 2 mid -> 1 root) renders
    `mid-one-summary-5/leaf-alpha-summary-1/pkg0-mod-py-1.md`, 0 absolute
    paths, and stays correct at collapse `levels=4`, `3` and `2` (at 2 the
    leaves correctly re-parent directly under the root).
  - **F20 reproduced on my own copy of `.e2e/run/.hrono/hrono.db`** (`.e2e/`
    never touched, mtime still Sep 3 20:54). The stored database IS F20's
    state: 7 nodes, all level 0, ids [1,2,4,5,8,9,10], **0** `node_children`,
    7 briefs. `hrono serve` on the copy -> `GET /trees/default/export` is
    **500** `{"code":"internal-error","message":"tree is not built to a single
    root: 7 nodes at its top level","details":{"tree":"default","level":0,
    "nodes":[1,2,4,5,8,9,10]}}`; `hrono tree export default -o ...` exits 1
    with that one line and writes 0 files.
  - **F19 reproduced.** Adding a level-1 root over the real 7 topics and
    restarting: `hrono tree export default -o exports/exp1` -> exit 0,
    **"Wrote 102 files"**, `find -type f` = **102** on disk, 7 `brief.md` in 7
    DISTINCT directories, `root.md` present with its child links, 0 files
    written anywhere outside the output directory. Dev's numbers are exact.
  - **No legitimate state I could find triggers the 500.** #114's drained leaf:
    one root at the top level, loads fine, and the orphan even renders into its
    own directory (see the note below). A single level-0 node and nothing above
    (the tiny-corpus case) loads and puts the root's own sections beside
    `root.md` relative — the F19 root-sections fix. An empty tree is still
    `None` -> clean 404. `build_tree:80-104`'s `_collect_root` runs
    unconditionally at the end of every build, including the non-reducing and
    D_MAX stops, so the PO's premise holds.

  **Blocking defect — `src/hrono/tree/commands.py:113-116`: a degenerate
  payload path escapes the refusal path as an unhandled `IsADirectoryError`,
  and one of the three cases is a REGRESSION from this commit.**
  `target = (out / entry["path"].lstrip("/")).resolve()` maps `"/"` (and `"."`
  and `""`) onto `out` itself; the guard's `base != target` is then False, so
  the entry is neither refused nor counted, and `target.write_text(...)` raises
  `IsADirectoryError` on the directory. `_run` (`commands.py:32-40`) catches
  only `ClientError` and `UnsafePath`, so it comes out of the CLI as a
  traceback. Driven through the real CLI with a three-entry manifest
  `[a.md, <degenerate>, b.md]`:

  ```
  exit=1  exception=IsADirectoryError  stdout=''
  on disk=['a.md']      b.md never written
  ```

  No "Wrote N files" line, no "refused N of M" line, and **every entry after
  the bad one is silently lost** — which is the exact F19 failure shape this
  ticket exists to remove, reintroduced for a different input class and with
  worse reporting than the case that was fixed. `"/"` specifically regressed:
  before the `lstrip`, `out / "/"` resolved to `/` and was cleanly refused;
  `"."` and `""` were already broken and are in scope because this commit
  rewrote the function and its contract.

  Not reachable through hrono's own renderer (`_slug` cannot produce these
  keys), but `_materialize`'s whole job is to handle a payload it does not
  trust — its docstring says so — and a crash is a denial of the export, not a
  refusal of one file.

  Fix, validated by me in a worktree: replace the guard with
  `if target == base or base not in target.parents:`. That refuses and counts
  all of `"/"`, `"."`, `""` and `".."`, leaves every legitimate path working
  (`'/ok.md'` -> `ok.md`, `'a/b.md'` -> `a/b.md`), and the full suite stays at
  **659 passed**. Please add a regression test alongside
  `test_a_refused_entry_does_not_cost_the_whole_export` covering a degenerate
  entry between two good ones, asserting both good files land and the refusal
  is counted.

  **Non-blocking judgements, for the record:**
  - **Collect-and-skip is the right call.** A partial export plus a non-zero
    exit and an exact count beats all-or-nothing here: the F19 harm was one bad
    entry costing the other 93; an export directory is a materialisation of a
    read-only map, not a transactional resource; and all-or-nothing would need
    staging plus an atomic rename, more machinery than the ticket asks for. The
    reporting is what makes it acceptable — "Wrote 1 file to <out>." then
    "refused 2 of 3 files that would write outside <out>: ..." — which is
    exactly why the blocking finding above matters: it is the one path that
    writes partially and reports nothing.
  - **Internal/500 for a forest is the right surface, with one caveat.** The
    message and `details` (tree, level, node ids) are genuinely useful — I
    pasted them straight out of the real corpus above. But the state is also
    reachable transiently mid-build: `build_tree` commits each level as it
    forms it and only calls `_collect_root` at the end, so a concurrent
    `GET /trees/{name}/export` between those points sees a multi-node top level
    and gets a 500. I drove that state (3 nodes at level 1, no root) and it
    500s. It is loud, accurate and strictly better than silently exporting one
    of them as the root, so it does not block — but a 500 for "a build is in
    progress" will read as a server fault. Worth a follow-up to distinguish
    "building" (409/503) from "build died half-way" (500); I have not ticketed
    it, since the PO may prefer to fold it into the #114/#115 batch.
  - **#114's harm is now overstated, in two places.** After this commit a
    drained orphan leaf DOES render into the export: I built the #114 shape and
    got `drained-leaf-born-after-the-build-3/brief.md` and its section file in
    the manifest, alongside the parented leaf. What it lacks is a link — the
    generated `root.md` Children list names only `original-leaf-1/brief.md`. So
    `src/hrono/tree/settle.py:29-31` ("stays out of ``export``") and #114's
    Context ("invisible ... to `export`") are now too strong; the accurate
    statement is "written to the export directory but unreachable by following
    the map from `root.md`". This ticket improved #114's symptom rather than
    worsening it — no action needed here, but #114's text should be corrected
    before someone designs its fix against the wrong harm.
  - Out of scope and untouched as instructed: #114, #113, #115, #102's
    `brief_upper.py` "Children:" list, and F21/F22's brief quality (the
    directory names on the real corpus are whole sentences, which is F21, not
    this ticket).
  - Commit `823b796` is a clean Conventional Commit, atomic, 8 files, no stray
    changes; the `.gitignore` line is still the pre-existing uncommitted one.
    `.e2e/` untouched — everything ran on copies in scratch.
- 2026-09-14 dev: **re-picked up after qa's FAIL**; fixed as `3f0df9a` on top of
  `823b796`. Nothing qa passed was reverted or redone.

  **Blocking defect — a path that resolves ONTO the output directory.**
  `tree/commands.py:113`: `if base != target and base not in target.parents:`
  became `if target == base or base not in target.parents:`. qa's proposed
  one-liner, evaluated and taken as-is: `"/"`, `"."` and `""` all lstrip/join to
  `out` itself, which the old clause treated as safe (`base != target` false),
  so the entry was neither written nor counted and `write_text` raised
  `IsADirectoryError` straight out of `_run` (which catches only `ClientError`
  and `UnsafePath`) — no "Wrote", no "refused", every later entry lost. The new
  clause refuses and counts all of `"/"`, `"."`, `""`, and still refuses `".."`.
  `"/"` was a regression introduced by my `lstrip("/")`, which is why it is
  fixed here and not deferred. `_materialize`'s docstring now states the rule it
  actually enforces: an entry is written only if it names a file STRICTLY under
  `out`.

  **Degenerate-path coverage** —
  `test_a_path_resolving_onto_the_output_directory_is_refused`, parametrized
  over `"/"`, `"."`, `""`, `".."`, `"/../"`, feeding `[a.md, <degenerate>,
  b.md]` through the real CLI. It asserts no exception escaped, exit 1, BOTH
  `a.md` and `b.md` on disk (the entry after the bad one is not lost), `out`
  still a directory, "Wrote 2 files" and "refused 1 of 3". Verified
  regression-grade: with the old clause restored the three that resolve onto
  `out` fail with `IsADirectoryError`; `".."` and `"/../"` pass either way (the
  old guard already caught those), which is the gap qa named — no test fed
  `_materialize` a path resolving TO the output directory.

  **#114's harm corrected in both places** (qa is right: my 096 work improved
  it, so the old wording overstates it).
  - `tree/settle.py:29-33` no longer says the leaf "stays out of export". It now
    says: it hangs under no parent, it IS still written to the export (#096
    gives every parentless node its own directory), but nothing links to it from
    `root.md`, so an agent walking the map from the root never reaches it.
  - The same correction in `.autodev/board/todo/114-...md`: a new "The exact
    harm, corrected 2026-09-14 after #096 landed" paragraph in Context, the
    visibility table row changed to "file written, but NOT reachable from
    `root.md`", and acceptance criterion 2 reworded from "appears in export" to
    "REACHABLE by following links from `root.md`" — so the attach-only fix the
    PO specified is designed against reachability, not against files on disk.

  **The docstring test was extended, since this is its second correction.** The
  new wording admits a cheap assertion and now carries one:
  `test_a_leaf_node_the_settle_drain_emits_is_briefed_not_parented` renders the
  export after the settle and asserts, for every drain-emitted leaf, that its
  `<slug>-<id>/brief.md` IS among the rendered files AND its directory is absent
  from `root.md` — plus a discriminating check that a PARENTED leaf's directory
  IS present in `root.md`, so the absence assertion cannot pass vacuously. The
  wording and the behaviour can no longer drift in either direction.

  **Filed, not fixed** (per qa and the file-it-don't-fix rule):
  - backlog **#116** — the #096 500 is reachable transiently mid-build
    (`build_tree` commits each level, `_collect_root` runs last), so "a build is
    in progress" currently reads as a server fault; wants 409/503 with the
    running-job check, keeping the 500 for a permanent forest.
  - backlog **#117** — `_materialize`'s write is still unguarded, so an
    `OSError` (a payload naming an existing directory, `a.md` then `a.md/b.md`,
    disk full, read-only output) still aborts mid-run and skips the report. Not
    reachable from hrono's own renderer (every key ends in `.md`, and a node
    directory can never equal a section file name), so it is robustness, not a
    live defect — deliberately out of this ticket.

  Real-corpus re-verification after the guard change, on the same scratch COPY
  (`.e2e/` untouched): `hrono serve` + `hrono tree export default -o
  exports/attempt2` -> exit 0, "Wrote 102 files", 102 files on disk, 7
  `brief.md`. The happy path is byte-for-byte what qa accepted.
  Gate clean: `ruff format` (222 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **664 passed** (659 + the 5 parametrized cases).
  Handing back to verifying.
- 2026-09-14 qa: **PASS — to po-review.** The blocking finding is fixed, the
  fix is regression-graded, and nothing I accepted at `823b796` regressed. Only
  `tree/commands.py` and `settle.py` changed in `src/` (8 and 5 lines), so the
  render/store work I already verified is untouched by construction.

  **The guard fix, driven through the real CLI.** All seven cases now behave
  identically and correctly — no exception escapes (only Typer's `SystemExit`),
  exit 1, BOTH good files on disk, `out` still a directory, and both report
  lines printed:

  ```
  '/'                 exit=1 disk=['a.md','b.md'] outIsDir=True
  '.'                 exit=1 disk=['a.md','b.md'] outIsDir=True
  ''                  exit=1 disk=['a.md','b.md'] outIsDir=True
  '..'                exit=1 disk=['a.md','b.md'] outIsDir=True
  '/../'              exit=1 disk=['a.md','b.md'] outIsDir=True
  '/../../etc/passwd' exit=1 disk=['a.md','b.md'] outIsDir=True
  'a/../../x.md'      exit=1 disk=['a.md','b.md'] outIsDir=True
  ...each: "Wrote 2 files to <out>." + "refused 1 of 3 files ...: '<path>'"
  ```

  Previously `/`, `.` and `""` came out as an unhandled `IsADirectoryError`
  with empty stdout and `b.md` lost.

  **Regression-grade, confirmed for exactly the three that discriminate.**
  Reverting `commands.py:112` to `823b796`'s `base != target and ...` in a
  worktree at `3f0df9a` (`PYTHONPATH` asserted inside it) fails precisely
  `test_a_path_resolving_onto_the_output_directory_is_refused[/]`, `[.]` and
  `[]` — 3 failed, 7 passed. Dev's statement that `..` and `/../` pass either
  way is exact.

  **On keeping those two params: keep them, they are not noise.** They pin the
  half of the guard that already worked, which is the live risk when a guard
  expression is rewritten — a future simplification that drops the
  `base not in target.parents` clause would sail past a test that only covered
  the newly-fixed inputs. Two extra parametrized cases, no extra fixtures. The
  distinction is documented in dev's own note rather than hidden, which is what
  makes it honest rather than padding.

  **The settle test's discriminating half really discriminates.** I mutated
  `render.py:73` so `root.md`'s child links no longer name the child's
  directory: the test fails on `assert [...]` -> `assert []`, i.e. the
  "a PARENTED leaf's directory IS in root.md" check is what stops
  `directory not in files["root.md"]` passing vacuously. I also mutated
  `render` to drop parentless nodes from the map entirely, and the other half
  fails too (on the `next()` that locates the emitted leaf's directory — it
  fails, though a `StopIteration` reads worse than an assertion would; style
  only).

  **#114's harm now matches what I measured, in both places.**
  `settle.py:31-33` says the leaf "is still written to the export (#096 gives
  every parentless node its own directory), but nothing links to it from
  ``root.md``, so an agent walking the map from the root never reaches it" —
  exactly the state I drove last tick (`drained-leaf-born-after-the-build-3/
  brief.md` present in the manifest; `root.md`'s Children list naming only
  `original-leaf-1/brief.md`). #114 carries a dated "exact harm" paragraph
  saying the same, its visibility table now reads "file written, but NOT
  reachable from `root.md`", and acceptance criterion 2 is reworded to
  REACHABLE-by-following-links. Correct on all three.

  **Happy path unchanged on the real corpus**, re-driven end to end on a copy
  of `.e2e/run/.hrono/hrono.db` (`.e2e/` untouched, mtime still Sep 3 20:54):
  `hrono serve` + `hrono tree export default -o ...` -> exit 0, **"Wrote 102
  files"**, 102 on disk, 7 `brief.md` in 7 distinct directories, `root.md`
  present. The stricter guard refuses none of the 102 legitimate keys.

  **On the two filings — both are well judged; #117's unreachability claim is
  correct and I checked it rather than took it.**
  - **#117**: the harm is real and reproduces on a hostile payload (`a.md` +
    `a.md/b.md` loses `c.md` and raises out of the command; so does
    `alpha-1/brief.md` + `alpha-1`). The claim that hrono's own renderer cannot
    produce it holds **by construction**: `render.py:161 _slug` is
    `re.sub(r"[^a-z0-9]+", "-", ...)`, so its output alphabet is `[a-z0-9-]`
    with no dot at all — I ran it over `a.md`, `node.md.md`, `A.MD`,
    `brief.md`, `../../etc`, `foo/bar`, `..`, `.`, `//` and a unicode case, and
    no result contains a dot or a slash. A directory component is
    `f"{slug}-{id}"` and a file key is `f"{...}.md"`, so a directory name can
    never equal a file name and no key can be a path-prefix of another. Stale
    files from an earlier export into the same directory cannot collide either,
    for the same reason. Backlog/low is the right call. One nit for whoever
    picks it up: the ticket says `a.md` then `a.md/b.md` raises
    `NotADirectoryError`; it is actually `FileExistsError`, from the `mkdir`.
  - **#116**: accurately describes the two meanings of one state, proposes
    409-vs-503 as a conventions question rather than taste, and its acceptance
    criterion 1 keeps the permanent-forest 500 loud — which is the thing that
    must not be lost. Low/small is right: it is ops noise and a false page, not
    a correctness bug. Matches what I drove last tick (3 nodes at level 1, no
    root -> 500).

  **Non-blocking nits, for whenever this file is next touched:**
  - `src/hrono/tree/settle.py:33-34` — the inserted sentence left the paragraph
    ragged: line 33 ends "The" and line 34 is the single word "closing". Ruff
    does not reflow docstrings, so it will stay that way.
  - `src/hrono/tree/commands.py:72-73` — the refusal message says "files that
    would write **outside** {out}", but the three degenerate paths write *onto*
    `out`, not outside it. The docstring now distinguishes the two classes; the
    user-facing line does not.

  Commit `3f0df9a` is a clean Conventional Commit ("fix: refuse an export path
  that resolves onto the output directory"), atomic, 4 files, no stray changes;
  the `.gitignore` line is still the pre-existing uncommitted one. #114, #113,
  #115, #116, #117, #102 and F21/F22 all left alone.

  Gate re-run by me on `3f0df9a`: `ruff format --check` 222 files unchanged,
  `ruff check` clean, `pytest` **664 passed** in 36.7s. All four acceptance
  criteria hold. Worktree removed, servers stopped, tree clean. Handing to the
  PO.
- 2026-09-14 PO: **ACCEPTED -> done.** Two commits (823b796 + 3f0df9a) close
  F19 and F20. Verified independently against a live server on a copy of the
  real corpus, not from the log.

  **Gate re-run by me:** `ruff format --check .` 222 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **664 passed** in 36.8s.

  **Both diffs read.** `_under` keeps the root's own sections relative; the
  `_directory` walk now terminates at the root rather than "while a parent
  exists", so only the root is `""` and every other node — parentless or not —
  owns an id-suffixed directory, which is what makes two briefs uncollidable.
  `_root` replaces `max(node_level, ...)` with a loud `Internal`. The final
  guard `if target == base or base not in target.parents` is correct by
  construction: a path strictly under `base` has `base` in its parents, and the
  equality arm catches the degenerate landings.

  **Driven end to end on a copy of `.e2e/run/.hrono/hrono.db`** — real server
  (`hrono serve` on the copy with the run's own master key), real CLI, real
  profile. `.e2e/` never modified; db and key mtimes still Sep 3.
  - **The stored state IS F20's forest** (7 nodes, all level 0, 0
    `node_children`). `GET /trees/default/export` -> **500**
    `{"code":"internal-error","message":"tree is not built to a single root: 7
    nodes at its top level","details":{"tree":"default","level":0,"nodes":
    [1,2,4,5,8,9,10]}}`, and `hrono tree export default -o ...` -> **exit 1**,
    that one line on stderr, **0 files**. Before this, the same call returned
    200 with six briefs silently gone. Loud beats lossy.
  - **Then the headline**, after adding a level-1 root over the real 7 topics by
    direct SQL (my own construction, not dev's helper) and restarting:
    `hrono tree export default -o <dir>` -> **exit 0**, "Wrote 102 files",
    **102 files on disk**, **7 `brief.md` in 7 DISTINCT directories**,
    `root.md` present, **0 files written anywhere outside the output
    directory**. In the original e2e run this exact command wrote ZERO files and
    exited 1.
  - **Manifest invariants over the live payload**: 102 entries, **0 absolute
    paths, 0 duplicate keys, 7 brief keys**, `root.md` present — and **all 7
    brief directories are linked from `root.md`**, so the map is not merely
    written, it is walkable.
  - **I probed the guard myself** with a 3-entry payload `[a.md, <hostile>,
    b.md]` over twelve inputs and a canary directory. All of `"/"`, `"."`,
    `""`, `".."`, `"/../"`, `"/../../CANARY/pwned.md"`, `"../escape.md"`,
    `"a/../../escape.md"` are refused AND counted, with **no exception**, both
    good files on disk every time, `out` still a directory, canary empty.
    Legitimate normalisation still works: `/etc/passwd` -> `out/etc/passwd`,
    `//x.md` -> `x.md`, `/ok.md` -> `ok.md`, `a/b/../c.md` -> `a/c.md`. The
    entry AFTER the bad one always lands — the F19 shape is gone at both layers.

  All four acceptance criteria hold. **The qa bounce was excellent work**: it
  found that dev's own `lstrip` had regressed `"/"` from cleanly-refused to an
  unhandled `IsADirectoryError` that ate every later entry — the exact failure
  this ticket exists to remove, reintroduced one input class over. Catching a
  fix that re-creates the bug in a neighbouring case is the whole point of the
  gate, and dev took the one-liner and graded it properly (the three
  discriminating params fail with the old clause restored; the two that pass
  either way are documented as such rather than passed off as new coverage).

  **Rulings on the four items:**
  1. **The split is CONFIRMED, and it is the right principle, not a
     convenience.** A forest AT THE TOP has no root: there is no entry point to
     the map, and choosing one arbitrarily is precisely what silently dropped
     six briefs in F20. That is unrenderable, so refusing loudly is correct. An
     unparented leaf BELOW the top is a different thing entirely — the tree
     still has exactly one root, the map is complete and walkable, and one
     branch is merely unlinked. Refusing the whole export for that would convert
     a partial-visibility bug (#114) into a total export outage: strictly worse
     for the user, and it would take the product's headline deliverable hostage
     to a known, ticketed, lesser defect. The general rule I want applied from
     here: **refuse what cannot be rendered correctly; degrade what can.**
     `test_an_unparented_leaf_below_the_root_still_loads` pins it.
  2. **#114's attach-only design still reads correctly — in fact the corrected
     harm STRENGTHENS it.** I checked the mechanism, not just the wording:
     `root.md`'s Children list is rendered mechanically from the tree's parent
     edges (I measured 7 of 7 brief directories linked on the real corpus), so
     **reachability is a direct function of the parent edge**. Attaching the
     leaf to a level-1 parent is therefore not merely a way to fix the symptom,
     it is the only thing that can produce the link. The design stands
     unchanged. One correction to my own wording of 2026-09-14: I closed that
     decision with "silently absent is not [acceptable]" — after #096 the file
     is not absent, it is present but unreachable. The conclusion is unaffected
     (unreachable-from-the-root is still the failure that matters, because an
     agent walks the map, it does not list the directory), and the ticket's
     Context, table and AC2 now say so. Good catch by qa; correcting a ticket's
     stated harm BEFORE someone designs against it is exactly right.
  3. **#116 and #117 both CONFIRMED as filings, both stay `backlog`/`low`.**
     #116 is a real ambiguity — one state, two meanings — and its AC1 correctly
     keeps the permanent-forest 500 loud, which is the part that must not be
     lost in making the transient case quieter. It is ops noise and a false
     page, not a correctness bug, so low is right. Note for the planned e2e
     re-run: an export issued mid-build will 500 with an accurate message; that
     is expected, not a new finding. #117 is robustness against a payload our
     own renderer provably cannot emit — qa verified the `_slug` alphabet has
     no dot or slash by construction rather than taking dev's word — so low is
     right, and it is the correct home for the remaining `_materialize`
     hardening. I have fixed the wrong exception name in it (see below).
  4. **Both nits: no new tickets, both routed to a file that will be edited
     anyway.**
     - The ragged `settle.py` paragraph is cosmetic and below ticket-worthiness;
       a card for it would cost more than the fix. Left as is, with a note added
       to **#114** — which rewrites exactly that paragraph when it lands — to
       reflow it then.
     - The refusal message saying "would write outside {out}" when the
       degenerate paths write ONTO it is a genuine (if unreachable) inaccuracy
       in a user-facing line, and "actionable error messages" is on our product
       bar. It belongs with the rest of `_materialize`'s hostile-payload work,
       so I have folded it into **#117** as an explicit acceptance criterion
       rather than spawning a one-line ticket.
