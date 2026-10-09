# E034 followups (minor, from qa round 1)

- An undone brief rewrite is stored as `hand-edited` with 0 tokens, so "Who wrote the brief" loses the model that wrote the restored text: `src/hrono/edits.py:198` (`undo` -> `_write_brief`); restore the replaced version's model/prompt/token fields from the kept E033 version, keeping the pin.
- Release ("hand back") leaves `edit_log` rows, so a later Undo re-pins a topic that was handed back, or puts the pre-rewrite text over a newer regeneration: `src/hrono/edits.py:228`; clear the topic's `edit_log` rows in `release`.
- `edit_log` grows without bound per topic (only undo clears it), though only the newest row is ever read: `src/hrono/edits.py:207` (`_record`); delete the topic's older rows when recording, or keep one row per node.
- A rename or rewrite to the same value still logs a row and offers an Undo that changes nothing: `src/hrono/edits.py:100`, `:126`; skip recording when the new value equals the old.
- Unrelated test edit: the unchanged-save test now writes its last save with model "t" instead of the default "m" (looks like a replace-all spill): `tests/summarize/test_brief_versions.py:110`; revert to `_write(conn, node, "text 5")`.
- No test pins that an undone brief stays pinned when the pin was released after the rewrite (the "brief restored by hand" pin is indistinguishable from the rewrite's pin in `test_undo_restores_the_old_brief_for_recall_too`): `tests/server/test_ui_node_edits.py`; release between rewrite and undo, then assert the pin.
- T1 and T2 landed as one commit (bc2ac90) rather than one per ticket.
