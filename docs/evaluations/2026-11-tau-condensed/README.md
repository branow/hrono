# TAU on condensation vectors (E056)

Question: `update` now places new sections by the blended condensation vector
(as a build clusters). Is `TAU` = 0.70 still the right bar there?

Setup: a copy of the flask bench tree (`flask` tree, 291 sections in leaf
topics, all condensations embedded by `embed`; the copy predated embedding
them, see below). One commit synced with `update` (one changed file, one new
file): 2 condense calls (claude-code, haiku). Script: `tau.py`; output:
`tau.out`.

Run on the real app, 2026-11-02:
- The log shows condense before placement (condensations stored 14:55:36, the
  placement row in `update_log` 14:55:41). Each placed section's clustering
  vector equals `clustering_vector(condensation vector, folder vector)` (the
  build's blend; difference 0.0).
- Own-centre similarity (the section against its topic's centroid, itself
  included): 73.5% of sections at or above 0.70, 26.5% below. Quartiles
  0.693, 0.765, 0.806.
- Leave-one-out (each section taken out and placed as if new): at TAU 0.70,
  49.5% land in their own topic, 18.2% in another, 32.3% park. Lowering TAU to
  0.55 parks 5.8% but sends 27.5% to another topic; raising it to 0.75 parks
  52.9%. There is no knee: the share placed in the wrong topic falls slowly
  while the parked share grows steadily.

Decision: TAU stays 0.70. The numbers do not point to a better value, and a
parked section is not lost: the run's drain or home pass places it
(`forced`), so a lower bar would only trade parked sections for wrong
topics. A measured change needs a larger tree with ground-truth topics, not
the 291-section flask copy.

Found on the way: the flask copy's 1312 older condensations were stored before
condensation bodies existed, so `embed` never vectorised them and old members
sat on raw vectors while new ones were placed on condensation vectors. `embed`
now registers a tree's condensation bodies first (`embed/op.py`); trees built
by current code are unaffected.
