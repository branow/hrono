# E030 followups (qa r1, minor)
- A build refusal for an unknown tree on an install whose earlier steps are open renders in the open step's box, titled "Not saved — nothing was changed" with a `config` field label (seen driving the real server: tree=nope landed in step 1, Connection), `src/hrono/server/ui/setup.py:238` -> render the refusal as a page-level notice, or make `_current` keep step=build for a refusal.
- After the refusal re-render the browser URL stays `/ui/setup/build`, so a reload re-posts the form, `src/hrono/server/ui/setup.py:238` -> redirect (303) to `/ui/setup?step=build` with the message, or accept that.
- The nowrap browser test injects its own 160px callout instead of measuring the real models-step callout, `tests/server/test_ui_browser.py:377` -> drive `/ui/setup?step=models` with the embed backend missing and measure that code span.
- Commit 7ba75e7 says the line is one command "across the README", but the README was not touched (it already matched) -> phrasing only.

# E030 followups (qa r1 rerun at 253f664)
- On an install with no connection yet, a refused `/ui/setup/build` (tree=nope) lands on step 1 under "Not saved — nothing was changed" with the message labelled `config`, not under the build step's "Not built — nothing was queued"; src/hrono/server/ui/setup.py:238 — render the refusal with a field-less problem and keep the build-step title, or say "Not built" whichever step opens.
# E030 followups (po review at cd31189)
- A refused `/ui/setup/build` for an unknown tree renders under whichever step is open (step 1 on a fresh install) with "Not saved" and a `config` label; only reachable by a hand-made post, so minor — src/hrono/server/ui/setup.py:238.
