# Acceptance 1: README does not mention insights

What the user did: read the README to learn how to set up model roles and
the new step.

What happened: "Models can be assigned per role (`condense`, `brief`,
`brief-upper`, `judge`)". There is no `insights` role, no word about the
step, the tree keys `insights`/`insights_threshold`, its cost, or when it
runs. Only `docs/api.md`, `docs/summarization.md` and `docs/dashboard.md` cover
it.

Expected: the README's Configuration names the optional `insights` role and
the per-tree switch, with one line on cost and on which run reviews.
