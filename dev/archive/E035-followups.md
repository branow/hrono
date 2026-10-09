# E035 followups (qa r1, minor)

- `who` in `_version_line` is set to "a hand rewrite" for a hand-written row but never used on that path; only `by` is read. `src/hrono/server/ui/nodes.py:428-429`. Fix: `by = "hand" if hand else str(row["model_name"])` and drop `who`.
- The leading-gap test `if number == 0 and (group[0][1] or group[0][3]) or number:` leans on and/or precedence. `src/hrono/server/ui/nodes.py:450`. Fix: write it as `if number or group[0][1] or group[0][3]:`.
- No test pins "replaced by a regeneration". Changing that string fails nothing. `src/hrono/server/ui/nodes.py:431`, tests/server/test_ui_node_edits.py. Fix: add a regen-replaced version to a page test and assert the phrase.
- `user-select: none` on the `.diff-*::before` rule does nothing: generated content is never selected, and removing it fails no test. `src/hrono/server/templates/base.html:373`. Fix: drop it, or keep it and say why.
- The README paragraph has a line well past the wrap width ("full old text behind Details; saving a brief unchanged keeps nothing. Its sections ..."). `README.md:110`. Fix: rewrap.
- Three tickets landed as one commit; CONTRIBUTING asks for one per ticket. Commit 1356a4c. Fix: none now, just keep to it next time.
