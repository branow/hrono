---
id: 162
title: a split silently releases the membership pins it destroys
priority: medium
size: small
depends_on: [155, 159]
spec_refs: [clustering-lifecycle.md]
---

## Context
Spun off from #159's qa review. A split retires the node it divides, and a
member of that node may carry a MEMBERSHIP pin anchored to it. #155's
`_restore_pinned` is built for a dead anchor: it follows the anchor's surviving
COMPANY — the other members — to whichever node inherited most of them, and
releases the pin only when "the topic is gone entirely".

After a split the company is gone too: every other member moved into the
children in the same operation. So `settle` reads a divided topic as a vanished
one and RELEASES the pin. Nothing tells the operator.

## Why this is worth a ticket
A pin is the one promise this product makes about hand-edits: what you fixed
stays fixed. Dropping one is defensible HERE — the operator did ask for the
topic to be re-divided, and #159 deliberately does not pin the children — but
"defensible" and "silent" together is how a trust feature stops being trusted.
The operator finds out weeks later, the way #125's orphans were found.

## The decision this ticket needs first
Which is right, and the ticket is small either way:
- **Re-anchor.** A pinned member's pin follows it into the child node that now
  holds it. The operator's "this belongs with those" survives a division they
  asked for, because the child IS the topic they pointed at, narrowed.
- **Release, but say so.** The split response reports which pins it released,
  and the reason. `hrono jobs get` already gives ops a place to report (#133),
  and this is a synchronous endpoint, so its body can carry it directly.

Lean re-anchor: it is what `_restore_pinned` already does for every OTHER way a
node can die, and a split is the one case where the successor is known exactly
rather than guessed — `repair.split` knows which child each member went to.

## Acceptance criteria
- [x] A section pinned into a node that is then split by hand keeps a pin that
      names a node that actually holds it (or is reported as released, per the
      decision above).
- [x] A `settle` run afterwards does not move that section.
- [x] The automatic over-MAX_CAP repair path behaves the same way as the manual
      one; a pin must not depend on who asked for the split.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Parenting and brief pins, which the `pins_follow_node` trigger already clears
with the node.

## Review log
- 2026-09-24 po: authored from #159's qa review.

- 2026-09-24 po: ruling — **re-anchor**, and the stakeholder confirmed it.

  It is what `_restore_pinned` already does for every other way a node can
  die: follow the anchor's surviving company to the node that inherited it.
  A split is the one case where no following is needed, because
  `repair.split` knows exactly which child each member went to — so the pin
  can be re-anchored at the moment of the split rather than reconstructed
  afterwards from evidence that the split itself destroyed.

  "Release, but say so" was the alternative and it is worse: it hands the
  operator a notification instead of the thing they asked for, and the reason
  it was ever tempting is that the release is what the code does TODAY, not
  that anyone chose it.

  Scope stays as authored: the automatic over-MAX_CAP path must behave the
  same way, because a pin cannot depend on who asked for the split.

- 2026-09-24 dev: picked up under the re-anchor ruling.

- 2026-09-24 dev: done, commit 97587ed. Re-anchor, as ruled.

  The change is inside `repair.split`, which is what makes the third criterion
  free: the automatic over-MAX_CAP path and the manual one are the same
  function, so a pin cannot depend on who asked. `split` already knows which
  child each member went to — it builds them — so the re-address happens at
  the moment the old anchor dies, with no reconstruction afterwards from
  company that the split itself scattered.

  `pins.reanchor` rather than `pins.pin`: re-pinning would rewrite `reason`
  and `pinned_at`. The operator's decision and its date have not changed, only
  the id that expresses it, so only `anchor_id` moves. A mutation proves it —
  swapping `reanchor` for `pin` leaves the chunk correctly placed and the
  reason overwritten, and the test fails on the reason.

  Driven live, the whole operator story:

      move section 17 -> node 1   200 {"from_node": 2, "pinned": true}
      split node 1                200 {"children": [3, 4, 5]}
      pins                        (17, "moved by hand", anchor 3)
      node 3 exists and holds chunk 17

  Mutations. Four run, one SURVIVED and was made to kill:
  - re-anchor nothing (the old behavior) -> 3 fail across repair, settle and
    the server flow.
  - `pin` instead of `reanchor` -> 1 fail on the preserved reason.
  - `reanchor` writing nothing -> 2 fail.
  - `anchored.get(id) == node_id` weakened to `id in anchored`, so a split
    re-addresses a pin that names some OTHER topic: SURVIVED. No test built a
    member whose pin points elsewhere, and hijacking another topic's decision
    is exactly the kind of thing that would be found months later. Added that
    member to the fixture and asserted its anchor is untouched; now kills.

  One seam note: the settle-level test injects `core_labeler` because the
  built corpus is smaller than the clustering floor, and its subject is the
  PIN. The REAL UMAP -> HDBSCAN recipe runs unseeded through the server test
  of the same flow, so the contract is covered by a real backend (#108).

  Gate clean: 1125 passed.

- 2026-09-24 qa: PASS, to po-review. All four criteria met, and the third one
  — "the automatic path behaves the same way" — is met structurally rather
  than by a second implementation, which is the right way to meet it: both
  callers are the same function, so there is nothing that could diverge.

  Gate re-run on a clean tree at 97587ed: 1125 passed, ruff clean. Commit is
  conventional, atomic, and carries the `pins.reanchor` addition that the
  change actually needs and nothing else.

  Re-ran dev's R2 (`pin` instead of `reanchor`): fails on the preserved
  reason, so the distinction is really guarded and not just described.

  Ran one they did not, aimed at the precise claim rather than the mechanism:
  re-anchor every pin to the FIRST child instead of the one holding it. Two
  tests fail — the repair-level one and the server flow — so "a node that
  actually holds it" is measured, not assumed. That is the assertion this
  ticket lives or dies on and it has teeth.

  Checked the one path dev reasoned about but did not observe: a pinned member
  that the clusterer calls NOISE reaches its child through the reattachment
  loop rather than through a core. Drove it with a labeler that marks the
  pinned section `-1`: the pin follows into the child that adopted it. It
  works because the noise is folded into the core groups BEFORE the children
  are built, so there is one loop and not two — worth recording, since a
  future edit that moved the reattachment after the child creation would break
  this silently and no test names the ordering.

  The interaction with #159 is consistent rather than contradictory: #159 says
  a split CREATES no pins, #162 says it DESTROYS none. `test_a_split_pins_
  nothing` still passes unchanged.

- 2026-09-24 po: CLOSED, first round. The ruling was re-anchor and the
  implementation found the reason the ruling was right: `split` does not need
  to RECONSTRUCT which topic the operator meant, it already knows, because it
  builds the children. `_restore_pinned`'s company-following is inference from
  evidence; this is a record kept at the moment the evidence still exists.

  `pins.reanchor` is the piece I did not ask for and would have missed. The
  reason on a pin is the only thing that survives the person who set it, and
  re-pinning would have quietly replaced "moved by hand" with whatever the
  pipeline was doing — a small loss, invisible, and exactly the kind this
  board keeps finding a month late.

  qa's note about the noise ordering goes into #163's context rather than a
  ticket of its own: it is a constraint on a function #163 will be editing,
  and it belongs where the next person to touch that loop will read it.

  M9's manual-edit surface is complete and every operation now holds what it
  touched THROUGH the pipeline, not merely at the moment of the edit — which
  was the milestone's actual promise and is a stronger statement than its
  ticket list made.
