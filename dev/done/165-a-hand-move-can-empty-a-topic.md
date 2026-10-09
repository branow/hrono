---
id: 165
title: a hand-move that empties a topic leaves its brief answering recall
priority: low
size: small
depends_on: [160, 125]
spec_refs: [clustering-lifecycle.md]
---

## Context
Filed by qa while verifying #160.

Moving the last section out of a topic leaves the node standing with no
members, and it keeps its brief and its `node://` passages. Recall can then
answer from the summary of a topic that contains nothing.

This is #125's harm with a clock on it. `repair`'s below-two rule retires an
empty node on the next run and the #125 trigger cleans its passages when it
dies, so the window is one `sync` rather than forever — which is why this is
`low` and did not block #160.

## The question
Whether an operator emptying a topic should be told, or the topic retired
there and then. Three options:

- Leave it: the pipeline already fixes it, and a topic that flickers empty for
  one cycle harms little.
- Retire it in the same transaction: the operator emptied it, so the intent is
  unambiguous; but it means a hand-move can delete a node, which is a bigger
  promise than "move this chunk".
- Report it: the move's response says the old topic is now empty, and the
  operator decides whether to dissolve it (#158 gives them the endpoint).

Report reads best — it keeps the operation small and puts the decision with
the person who has the context.

## Acceptance criteria
- [x] Decided and implemented, with a test that a topic emptied by hand does
      not answer recall from a stale summary once the chosen mechanism runs.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-24 qa: filed from #160 verification.

- 2026-09-26 dev: done, commit b90402f. **Report**, as the ticket leaned and
  #167 had just set the pattern for.

  "Retire it in the same transaction" was the tempting one and it is wrong for
  the reason the ticket gives: a hand-move that can DELETE a node is a bigger
  promise than "move this chunk", and an operator who wanted the topic gone has
  an endpoint for that. "Leave it" is defensible — the pipeline does fix it —
  but the person holding the context is the one who just made the change, and
  they only get to act on it if somebody tells them.

  `move_section` returns a `Move` now rather than a bare id: what it did, and
  what it left behind. The route turns `emptied` into the note, and says
  nothing when nothing was emptied — same discipline as #167, because a note
  on every move is noise that teaches people to skip notes.

  Driven on a real server, a topic holding one section:

      {"section_id":2,"from_node":2,"to_node":1,"pinned":true,
       "note":"topic 2 is now empty; it still answers recall from its summary
               until a repair run retires it, or dissolve it here"}

  The AC asked for a test that the emptied topic stops answering recall "once
  the chosen mechanism runs", and with `report` the mechanism is the operator
  acting on it. So the test drives the whole loop the note points at: the topic
  still has its `node://` passages after the move (the note is TRUE), and after
  a dissolve it has none — which is #125's trigger doing the work, so the note
  points somewhere that actually resolves it.

  Mutations, all killed: the move never noticing it emptied a topic -> 1 fail;
  a note on every move -> 1; the route dropping the note -> 1.

  Gate clean: 1173 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review, with one test added rather than a round
  trip — it was a missing guard on correct code and I had the mutation in hand.

  Gate at b90402f + the test commit: ruff clean, 1174 passed. Re-ran dev's
  three mutations; all fail as stated. Drove the note on a real server against
  a topic holding one section and it reads exactly as intended.

  **The mutation dev did not run:** flip `emptied` so a chunk from the PENDING
  POOL counts as having emptied a topic. It SURVIVED. A parked chunk came from
  no topic (#164), so `from_node` is null and the note would have read "topic
  None is now empty" — nonsense, shown to an operator, in the one place this
  ticket exists to put a sentence they can act on. The behaviour was already
  right; nothing pinned it. `test_a_chunk_from_the_pool_empties_nothing` now
  does, and the mutation fails.

  That is the two newest features of this milestone meeting each other — #164's
  pooled chunk and #165's note — and neither ticket's tests thought about the
  other. Worth remembering when the next small feature lands on the same
  endpoint.

  The third test is the one I would have asked for: it drives the whole loop
  the note POINTS at, so the sentence is verified to be both true when written
  and resolvable by the thing it recommends.

- 2026-09-26 po: CLOSED. Report, and the note is a sentence an operator can act
  on rather than a status they have to interpret.

  The decision I want on record is the one NOT taken. Retiring the topic in the
  same transaction would have closed the ticket in fewer lines and made
  `move a section` into an operation that can delete a topic. The endpoint's
  name is its contract, and a surprise inside it is how operators stop trusting
  a tool. Telling them and leaving the decision where the context is costs one
  sentence.

  qa's finding — a pooled chunk reporting "topic None is now empty" — is the
  shape to watch now that this milestone has many small operations on the same
  surface: #164 and #165 are both new, both correct, and neither ticket's tests
  considered the other. That is not a process failure, it is what happens when
  features arrive one at a time; the answer is exactly what qa did, which is to
  mutate at the seam between them rather than inside either.

  The `note` field now appears on two endpoints (#167's delete, this move) with
  the same discipline: only when there is a consequence, and phrased as what to
  do about it. That is a convention forming. I am not writing it down after two
  instances — but a third makes it a rule.
