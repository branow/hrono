---
id: 061
title: `brief-upper` pure-abstraction op (T22.2)
priority: high
size: medium
depends_on: [060, 057, 021]
spec_refs: [build-order.md#T22.2, summarization-experiments.md, implementation-notes.md]
---

## Context
T22.2. An upper-level node summarizes its CHILD BRIEFS, not source sections —
there is no condense stage above level 1. summarization-experiments validated
this ("level2 = summarize the summaries WORKS, kept for parent nodes"): a parent
brief built from the six child node summaries was good, with per-child
discriminative lines. This is the `brief-upper` op, distinct from `brief` (#059)
because its input is child briefs and it uses the compact `brief-upper`-role
prompt (seeded #021), which is the pure-abstraction flavor rather than the full
adaptive reduce.

## Description
Register a `brief-upper` job op that writes the brief for each upper-level node
(level >= 2) from its child briefs:
- Resolve the `brief-upper`-role model + the seeded `brief-upper`-role prompt +
  connection; call via #057. (Same role->model open question / default as #058.)
- Per upper node: gather its member CHILD nodes' briefs (#059 / recursive), render
  the brief-upper prompt over them, write the node's brief with provenance
  (model, prompt+hash, tokens) exactly like #059.
- References mechanical: append child node identities from membership in code.
- Discriminative per-child lines are a property of the seeded prompt, not code.
- Lock discipline + failure isolation + skip-on-unchanged, same as #059.
- PLACEHOLDER (from #066): the prompts registry now REQUIRES a `brief-upper`
  template to contain `{content}` (that is where condense/brief inject, and the
  seeded brief-upper default uses it). Inject the child briefs at `{content}` to
  match; if you choose a different token, update `_REQUIRED_PLACEHOLDERS` and the
  seeded default together in the same commit, or the validator will reject edits.

## Acceptance criteria
- [ ] `brief-upper` runs as a job over upper-level nodes and writes one brief per
      node from its child briefs (not from sections).
- [ ] Uses the seeded `brief-upper`-role prompt via #057; provenance recorded
      like #059; child references appended mechanically.
- [ ] LLM outside the #008 lock; failing node isolates; re-run over unchanged
      nodes makes zero new LLM calls.
- [ ] Tests (fake client): a two-level fixture (child briefs -> parent brief)
      writes a parent brief citing its children, provenance recorded, skip-on-
      unchanged. `ruff format`, `ruff check --fix`, `pytest` clean; committed.

## Out of scope
- The recursion-to-root controller that decides when to stop (T22.3 / #062).
- Level-1 `brief` from condensations (#059) — this is strictly the >= level-2
  case over child briefs.

## Review log
- 2026-08-23 PO: authored as T22.2. Pure-abstraction reduce over child briefs
  (level2 validated in the experiments), compact brief-upper prompt (seeded),
  same provenance + mechanical-reference + outside-the-lock discipline as #059.
- 2026-08-24 dev: DONE, committed f621cb6, handoff to qa. Added `brief-upper` op
  (summarize/brief_upper.py) + briefs.child_briefs / briefs.child_ids. Writes one
  brief per upper node (scope level, default 1 — the first node-of-nodes level in
  the 0-indexed scheme; the ticket's "level>=2" is 1-indexed) from its CHILD
  briefs (node_children -> child briefs), via the seeded brief-upper prompt (#057
  client). Child refs appended mechanically ("Children:\n- node <id>"), provenance
  + member-set signature recorded like #059/#064, LLM outside the #008 lock,
  per-node persist so a failing node isolates and a re-run over unchanged makes
  zero calls. {content} placeholder matches #066's requirement. Reuses
  stale_or_missing/member_signature so #064 invalidation covers upper levels too.
  Verified: ruff clean; pytest 441 passed / 1 skip (+6: parent-from-children,
  input-is-child-briefs, mechanical child refs, zero-call re-run, failure
  isolation, registration).
- 2026-08-24 qa: PASS (commit f621cb6) -> po-review, with a PROCESS ESCALATION
  (below). Gated 061's commit in ISOLATION via a throwaway git worktree at
  f621cb6 (NOT a stash — see escalation): ruff format/check clean, full suite 441
  passed / 1 skip, summarize+levels 34 passed. The commit is correct:
  - brief-upper is a faithful parallel of #059's brief op over CHILD BRIEFS
    instead of condensations: resolves the seeded `brief-upper` prompt + text
    model, renders child briefs at `{content}`, appends child node ids
    mechanically ("Children:\n- node <id>"), records provenance (model, prompt
    name + hash, tokens) + member-set signature, per-node persist. Tests confirm:
    2 level-1 parents each briefed from their child briefs, input is child briefs
    (not sections), mechanical child refs, zero-call re-run, failure isolation.
  - Correctly reuses #064's `stale_or_missing` + `member_signature` (which prefix
    child ids `n<id>`), so upper-level briefs get incremental invalidation too.
  - Closes the loop with my #066 note: #061 injects at `{content}`, matching the
    validator's required placeholder for `brief-upper` and the seeded default — so
    #066's forward guard is satisfied, not violated.
  - Level default 1 (0-indexed first node-of-nodes level) lines up with #060,
    which builds level source+1 (default source 0 -> level 1).

  PROCESS ESCALATION (PO — 5th occurrence of the recurring hygiene problem):
  when 061 arrived in verifying, dev had ALREADY started the NEXT ticket's WIP
  (#063 faithfulness gate) uncommitted in the shared tree — new faithfulness.py,
  migration 0014_brief_unfaithful.sql, test_faithfulness.py, and edits to
  briefs.py (`upsert`/`get` gain an `unfaithful` column), brief.py, brief_upper.py.
  That WIP made a bare `uv run ruff check` RED (E501 in the WIP's faithfulness.py:
  18) and a bare `uv run pytest` ran against a polluted tree — neither is a valid
  061 signal. I isolated with a worktree at 061's commit (441 passed, ruff clean)
  and did NOT touch dev's WIP. NOTE FOR THE LOOP: this is also what happened on
  #060 — there I used `git stash`, which briefly removed dev's uncommitted files
  and disrupted their concurrent edit (dev read it as a `git reset`); a worktree
  is the correct non-disruptive isolation and I've switched to it. Please have dev
  commit AND route each ticket, leaving the tree clean, before starting the next
  ticket's WIP. Also: the in-flight #063 WIP currently has a ruff E501 in
  faithfulness.py:18 — must be fixed before #063 hands off. (Pre-existing
  unrelated `.gitignore` edit also still uncommitted.)
- 2026-08-24 PO review: PASS -> done. Gated #061's commit (f621cb6) in ISOLATION
  via a throwaway worktree (the tree at HEAD had #063's faithfulness integration
  layered onto brief_upper.py, so the working-tree file is NOT #061's version):
  confirmed f621cb6's brief_upper.py does NOT import faithfulness — that is #063's
  later addition. In the worktree: ruff clean, 70 summarize+cluster tests pass.
  Read the f621cb6 code: a faithful parallel of #059 over CHILD briefs — resolves
  the seeded brief-upper prompt + text model, injects child briefs at `{content}`
  (satisfies #066's guard), appends child node ids mechanically ("Children:"),
  records provenance + member-set signature, per-node persist, reuses #064's
  stale_or_missing/member_signature so upper levels get incremental invalidation.
  Level default 1 aligns with #060's level source+1. All acceptance criteria met.
  Closed.
  PROCESS: qa independently switched from `git stash` to a throwaway WORKTREE for
  isolation — the exact fix I recommended to the stakeholder, and non-disruptive
  to a concurrent dev (unlike stash, which #060 showed can disrupt live edits). I
  used a worktree here too. The team is converging on worktree-per-ticket even
  before the stakeholder decision; that decision would make it the default rather
  than a per-review workaround.
