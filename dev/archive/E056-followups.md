# E056 followups (qa r1)
- `_register_condensations` returns early for the unscoped default tree, so its pre-body condensations are never embedded and old members stay on raw vectors (`src/hrono/embed/op.py:80`); fix: register every condensation when `sources_of` is None.
- `_register_condensations` registers condensations of every model, not only the current condense model, so old-model condensations get embedded for nothing (`src/hrono/embed/op.py:84`); fix: filter by `condense_model(conn)`.
- With two text models and no `condense` role the outcome reads "no condense model: placed by the raw vector (multiple text models - give one a role (condense))"; a build fails in the same setup (`src/hrono/tree/update.py:140`); fix: decide whether an ambiguous model should fail the sync like the build.
- (po 2026-11-02: all three folded into E061.)
