---
id: E035
title: a brief's previous versions read right and copy back clean
priority: medium
depends_on: [E033]
requirements: [60]
---

## Goal
E033's version list on the topic page misreads after two hand rewrites, keeps
blank versions, and pastes diff markers when copied. Fix what a curator hits.

## Tickets

### 1 each version says who wrote it, what replaced it, and when
Change: one line per version, e.g. "by model-1 (Oct 3), replaced by a hand
rewrite (Oct 4)"; show `written_at` next to the replacement time.
Done when:
- [ ] two hand rewrites in a row never render "by by hand"; a test pins it
- [ ] model-written and hand-written versions each read right
Look at: src/hrono/server/ui/nodes.py:413-420, templates/node.html:364

### 2 an unchanged save keeps no version
Change: `_keep_replaced` skips the copy when the new text equals the stored.
Done when:
- [ ] saving a brief unchanged (or an identical regen) adds no version and
  pushes none out of the five
Look at: src/hrono/summarize/briefs.py:503

### 3 an old version copies back without markers or gaps
Change: render `+`/`-` as CSS or a separate span, not in the line text; a
faint separator between hunks; the full old text behind a Details.
Done when:
- [ ] selected text of a diff line holds no marker (browser test)
- [ ] a long brief shows a separator where lines were skipped, and the full
  old text is one click away
Look at: src/hrono/server/ui/nodes.py:418-428, templates/node.html

## Out of scope
- regrouping the `.diff-*` CSS rules (taste)

## Log
- 2026-10-04 po: created from backlog/E033-followups.md (qa r1 + po review). Waits on E033 (same files); runs before E034 (also nodes.py/node.html).
- 2026-10-04 po: started; E033 merged (bd36a48).
- 2026-10-04 dev r1: tickets 1-3 in one commit; tests: version line, no by-by-hand, unchanged save, browser copy+gaps+full text; mutations: unchanged guard, gap between hunks (both failed tests).
- 2026-10-04 qa r1: pass at 1356a4c; drove the topic page in Chromium (two hand rewrites through the Brief form, then an unchanged save: versions 1, 2, 2; lines read "by scribe-9 (...)" and "by hand (...)"; the copied diff selection has no markers; 3 dashed gaps; Full text opens the old brief). Re-ran dev's unchanged-guard mutation, plus my own on by-hand, the marker moved into the text, and the trailing gap: each failed a test. 259 affected tests and 935 server/tree/cluster tests pass. Followups in backlog/E035-followups.md.
- 2026-10-04 po review: accept at 1356a4c; all Done-when met by qa's drive (by-hand line, unchanged save keeps none, marker-free copy, gaps, full text). Minors stay in backlog/E035-followups.md.
- merged to main at 1356a4c
