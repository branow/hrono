# E040 followups (qa round 1, head 3fc4a85)
- The rebrief test fakes the change with `UPDATE passages SET uri = uri || 'x'`, and its comment says a rebrief always gives a new uri; a brief passage's version is its member-set signature (src/hrono/recall/brief_passages.py:67), so a rebrief that keeps its members keeps its uri and shows as same/moved. Fix the comment at tests/server/test_ui_ask.py:285, and drive one case through a real re-brief.
- `round(hit.score, 3)` in `snapshot` (src/hrono/server/ui/ask_history.py:86) survives mutation; add a test that the stored score is rounded, or drop the rounding.
- The dropped-out label cuts the path mid-word ("atch/run/src-repo/f7.txt 0") at src/hrono/server/ui/ask_history.py:148; cut at a `/`, or show the file name.
- The "lives in this browser only" hint only shows once there is history (templates/ask.html:27, inside `{% if asked %}`); a first-time visitor never sees it before the cookie is set. Show it beside the form too.
- A passage whose source version changed shows up as both new and dropped with the same path and range (the key includes the version, ask_history.py:91). Consider a "changed" status for the same path and range under a new version.
# E040 followups (qa round 3, dec1bbf)

- A file name longer than LABEL (24) still gets cut mid-word, since `_label` only cuts at a `/` inside the kept tail: `src/hrono/server/ui/ask_history.py:168`. Fix: when the tail has no `/`, show the whole file name (the part after the last `/`).

# E040 followups (qa restart round 1, head 71391c2)

- A dropped-out label is no longer capped at 24 chars, so a long file name (80 chars) runs past its `<li>` at 375px (li clientWidth 303, text right edge 650): `src/hrono/server/templates/ask.html:94`. Fix: give `#dropped li` `overflow-wrap: anywhere` (as `.section-head .mono` does in base.html:808). The page already scrolls sideways at that width for the same file from the passage's own path line (`div.mono.small`) and the tabs, which predates E040.
- `_label` nests an if/else inside the length guard: `src/hrono/server/ui/ask_history.py:169`. Fix: early-return the short/boundary case, then `return` the tail cut at `/` or the file name, flat.

# E040 followups (qa restart round 2, head ba9a313)

- Commit ba9a313 carries a `Co-Authored-By` body; CONTRIBUTING/qa rule is one sentence, no body, no attribution. Fix: drop the trailer when the epic's commits are squashed/merged, and keep it out of future dev commits.
