---
id: 167
title: the registry engine needs a delete hook; removing a tree's config arms a full recluster
priority: medium
size: small
depends_on: [054, 012]
spec_refs: [implementation-notes.md]
---

## Context
From #054's dev flag and qa review, ruled into its own ticket by the PO.

`Descriptor` has a `validate` hook for WRITES and nothing for deletes, so the
engine's generic DELETE cannot be refused or qualified per collection. The
motivating case: `hrono tree config rm alpha` (or `DELETE /trees/alpha`) returns
alpha to the UNSCOPED state, so the next `maintain alpha` clusters every source
in the corpus into it. One small config row silently arms a very large
operation.

The meaning of an absent row is RIGHT and must not change — None means
unscoped, which is what makes the `trees` collection additive over every
existing database (#054). What is wrong is that nothing tells the operator what
their delete just enabled.

## Why a hook rather than a special case
"May this be deleted, and what should the caller be told" is a question more
than one collection will have:
- a `models` entry a `trees` or `sources` row still references;
- a `connections` entry a source still authenticates with;
- this tree case, where deletion is legal but consequential.

A per-collection branch in the engine is what `Descriptor` exists to avoid
(#012): a new collection is a descriptor, never a new branch.

## What it needs
- A `before_delete` hook on `Descriptor`, same shape as `validate`: it may
  raise to refuse, and the engine turns that into the usual envelope.
- For `trees`: not a refusal — a tree whose config is deleted is a legitimate
  thing to want. Either require an explicit confirmation the way `hrono reset`
  does (#034 set that precedent for "never silent"), or report in the response
  what the tree now maps (everything) so the next `maintain` is not a surprise.
- Decide whether a tree with NODES may have its config deleted at all.

## Acceptance criteria
- [x] Deleting a tree's config cannot silently leave it unscoped: the operator
      is told, or asked, per the decision above.
- [x] The hook is data on the descriptor, with no per-collection branch in the
      engine.
- [x] A collection with no hook behaves exactly as today.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-25 po: authored from #054's dev flag and qa review.

- 2026-09-26 dev: done. `before_delete` is one optional field on `Descriptor`,
  same shape as `validate` — it may RAISE to refuse, and it may return a note.
  No branch in the engine for any collection; a descriptor that declares none
  behaves byte-for-byte as before, which a test asserts against `sources`.

  **Report, not refuse, and the ticket was right about that.** Wanting a tree
  unscoped again is legitimate and the config is one PUT away from coming back.
  What was missing was that the operator hears it, and hears it where they
  actually are — so the CLI prints the note under the confirmation:

      $ hrono tree config rm default
      Deleted trees/default.
      tree default now maps EVERY source: the next maintain will cluster the
      whole corpus into it, over the 5 topic(s) it holds today

  The note is silent when the tree holds no topics: there is no consequence to
  warn about, and a note every time is noise that teaches people to skip notes.
  A test pins both halves.

  On "whether a tree with NODES may have its config deleted at all" — yes. The
  count is what makes the note worth reading (5 topics, not "a tree"), so the
  thing that might have justified a refusal is the thing that makes reporting
  enough.

  Mutations, all killed: the engine never asking the hook -> 1 fail; the hook
  never having anything to say -> 1; a note on every delete including an empty
  tree -> 1.

  Gate clean: 1163 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review. Gate at ed3b0e3: ruff clean, 1163 passed.
  Re-ran dev's A1 (the engine never asking the hook) — fails.

  Drove the CLI myself against a real server holding a built tree, and the note
  lands where an operator actually reads it:

      Deleted trees/default.
      tree default now maps EVERY source: the next maintain will cluster the
      whole corpus into it, over the 5 topic(s) it holds today

  The count is what makes it worth reading. "This tree is now unscoped" is a
  sentence people skim; "over the 5 topics it holds today" is one they stop at.

  Checked the half of the contract nothing uses yet — the comment says the hook
  "may RAISE to refuse", and a claim in a comment is worth as much as the code
  behind it. Built a descriptor whose hook raises `ValidationFailed` and drove
  a delete: **400 with the hook's own message, and the row still there.** True
  by construction rather than by care — the engine simply does not catch, and
  `ValidationFailed` is a `BadRequest` — but now confirmed rather than assumed.

  One asymmetry worth naming, not a defect: a seeded default RESETS rather than
  deletes, and that branch returns before the hook is reached. Correct as
  written — a reset is not a delete — but the next collection to want a hook
  may also have defaults, and then "before_delete" will need to say which it
  means. `trees` has no defaults, so nothing turns on it today.

- 2026-09-26 po: CLOSED. The footgun #054 left is closed the way it should
  be — by telling the operator, not by forbidding them.

  The judgement I want kept is the silence. A note on every delete would have
  satisfied the ticket and made things worse: people learn to skip a line that
  is always there. It appears only when there is a consequence, and it carries
  the COUNT, which is what turns a sentence someone skims into one they stop
  at.

  qa checking the raise path was right even though nothing uses it. The comment
  on the descriptor claims that capability, and a claim in a comment is worth
  what the code behind it is worth — the next person to need a refusal will
  read that comment and trust it.

  The reset-versus-delete asymmetry goes in the backlog as a NOTE on the hook
  rather than a ticket: it is correct today, `trees` has no defaults, and
  authoring work against a collection that does not exist yet is the
  speculative structure the conventions forbid.
