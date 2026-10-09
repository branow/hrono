---
id: E043
title: preview an edited prompt on one topic before applying it
priority: medium
depends_on: []
requirements: [68]
---

## Goal
Changing a prompt makes every brief it wrote stale and costs a full re-brief.
A curator should first see what the new prompt writes for one topic, next to
the current brief, and only then save it.

## Tickets

### 431 a prompt edit can be previewed on one chosen topic
Change: on the prompt's Settings form, "Preview on topic" runs the unsaved
prompt on one topic as a POSTed job (same model, same inputs as a real brief)
and shows the result beside the current brief. Nothing is stored in the tree,
no config changes; the spend is recorded like any run.
Done when:
- [ ] preview shows new vs current brief; tree and config are byte-identical after
- [ ] the job's cost appears on Usage; a failed preview says why
- [ ] Save afterwards still shows the usual invalidation preview
Look at: src/hrono/server/ui/settings.py, templates/config.html, summarize/resolve.py

## Out of scope
- previewing on more than one topic at once

## Log
- 2026-10-04 po: created from REQUIREMENTS 68.
- 2026-10-04 dev: round 1 started, worktree .claude/worktrees/E043.
- 2026-10-04 dev: 431 32b0cd0 brief-preview op + Preview on topic on the prompt form; tests: tests/summarize/test_brief_preview.py, test_ui_settings.py (real HTTP stub model); drove it in Chromium (evidence/E043); mutations run: stores-reply, no role gate, saves, offstage, lost typed text, level check, empty check, template unused, unledgered seam, all caught.
- 2026-10-04 qa: round 1 FAIL at 32b0cd0. Drove add/edit prompt -> Preview on topic -> result beside current brief -> Preview impact -> failed preview (model down) in Chromium, tree/registry/brief_versions hashes unchanged, Usage lists the job. Re-ran dev's stores-reply mutation (caught) and my level-check drop (caught); my mutation dropping the failure reason from the panel survived: test_a_failed_preview_says_why does not assert the why. Followups: backlog/E043-followups.md.
- round 2: 45da64f failed-preview test asserts the explained reason; mutation (empty <p>) now fails it, restored.
- qa round 2 PASS at 45da64f: the round-1 finding is fixed (test_a_failed_preview_says_why now asserts the explained reason). Re-ran the empty-<p> mutation and a drop-the-next-step mutation on config.html; both are caught. Ruff clean; tests/summarize+server+jobs 1105 passed, 1 skipped. Followups in backlog/E043-followups.md.
- 2026-10-04 po: review ACCEPT at 45da64f. All three Done-when met per qa's driven run (tree/config hashes unchanged, Usage lists the job, failure reason shown, Preview impact still works); README + guide updated. qa's minor findings stay in backlog/E043-followups.md.
- merged to main at f9af2bc
