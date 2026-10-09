# E036 followups (qa round 1, bc25ca4)

- Commit: three tickets landed as one `fix:` commit; the convention is one Conventional Commit per ticket. src/hrono/edits.py (whole diff). Split per ticket next time.
- `_write_brief` spreads a mixed-type dict into `briefs.upsert` and silences it with `# type: ignore[arg-type]` at src/hrono/edits.py:157. Pass the fields explicitly (or a small typed record) so the type checker keeps checking them.

# qa round 2, 7bea1d9

- `test_an_undone_rewrite_of_an_unknown_record_is_rebriefed` (tests/server/test_ui_node_edits.py:549) is vacuous: the fixture brief is already stale (its stored signature is "sig", and its text trips the shape guard), so blanking the kept `member_signature` changes nothing. The mutation "restore with the current signature instead of the kept one" in src/hrono/edits.py:151 survives the whole file. Fix: seed a brief with the long text and the real signature (as the test above it does), set the kept signature to a different value, and assert `stale_or_missing` lists the node; qa checked that such a test fails under the mutation.

# po review, 7bea1d9

- An undone rewrite of a brief kept before migration 0041 restores model_name only (prompt '' / tokens 0) while README says it "goes back to the model and prompt that wrote it"; acceptable for legacy rows, but the README line could say "when hrono kept it".
