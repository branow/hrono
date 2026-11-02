# E061 followups (qa, 2026-11-02)
- Commit 09e6e72 carries the board move `dev/todo -> dev/in-dev` of the epic file; at merge keep main's board side (drop the branch's rename) so the rebase does not leave a stale copy in `dev/in-dev/`.
- A non-numeric value posted to a number field (`f.insights_threshold=abc` or `500,000`) answers 500 (`src/hrono/server/forms.py:402` `_number`); raise a field error and re-render the form like `-3` does. Pre-existing; a raw POST only, the browser's number input blocks it.
- `examples=["500,000"]` on the int `insights_threshold` (`src/hrono/registry/collections/trees.py:73`) puts a string example into the field's JSON schema; give the form its placeholder from a form-only hint (or `json_schema_extra`) and keep the schema example an int.
- The uk form shows the placeholder as `500,000` (`trees.py:73`); format it per locale (`500 000`).
- An unscoped tree's embed takes every missing body (`src/hrono/embed/op.py:131`, `_allowed` returns None), so another model's condensation whose body was stored but never embedded (a run stopped between condense and embed, then the condense model changed) is still embedded; filter condensation bodies of other models out of the unscoped path too.
- The card holding the failed-review callout is headed "Findings 0"; next to "did not finish" the 0 reads as "nothing found". Hide the count when the last review failed (critique.md).

(po 2026-11-02: all left here for the acceptance pass; a gap acceptance finds in O4 or O6 folds these into one epic with it. The unscoped other-model condensation needs a run stopped between condense and embed and a condense model change; the 500 is a raw POST the browser blocks.)
