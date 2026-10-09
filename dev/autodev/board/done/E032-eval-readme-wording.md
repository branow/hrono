---
id: E032
title: the eval README's redaction sentence reads right for stderr
priority: low
depends_on: [E031]
requirements: []
---

## Goal
Minor wording finding on E031: the README says stderr output is redacted
"before they are written", which reads oddly for a printed report.

## Tickets

### 1 "written or printed"
Change: the redaction sentence says "before they are written or printed".
Done when:
- [ ] .e2e/eval/README.md:97-99 reads "written or printed", lines within 80 columns
Look at: .e2e/eval/README.md

## Out of scope
- any change to what is redacted

## Log
- 2026-10-04 po: created from backlog/E031-followups.md (qa r1). The other two lines (log the handed-over head; one commit per ticket) are process notes, not work.
- 2026-10-04 dev r1: ticket 1 0d6efcb; read lines 97-100, longest line under 80; docs-only, no mutation applicable.
- 2026-10-04 po: orphaned in verifying at 0d6efcb (run stopped); restarted.
- 2026-10-04 qa r1: pass at 0d6efcb; read .e2e/eval/README.md:97-100 at head (no line over 80), confirmed run.py:168-171 redacts both isolation.json and the stderr report so "written or printed" is true; docs-only, no mutation applicable; no followups.
- 2026-10-04 po: accept at 0d6efcb; README:99-100 reads "written or printed", all lines <= 80, claim true per run.py:168-171. No followups (polish on polish dropped).
- dev merge: ff-merged to main, head 0d6efcb
