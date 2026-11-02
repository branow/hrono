# E058 followups (qa r1)

- `reviewing=False` in `src/hrono/tree/sync_chain.py:180` has no test: setting it True leaves the suite green (`test_a_sync_does_not_spend_on_passes_unasked` calls `build_tree` directly); E059 replaces this guard, so give its sync drive the assertion.
- The export's root page keeps only the root brief's opening (`src/hrono/export/render.py:_routing`), so the root pass's findings (placed under Hazards and Conventions) never reach `root.md`; they reach recall and the node page only. PO: decide whether the root's extension belongs on `root.md` or the root pass should place its findings in the opening.
- The node page's "Built" date for an extended topic is the node's creation date, not the extended brief's (`/ui/trees/flask/nodes/17` shows 2026-10-10); E060 should show "extended by insights" with its date.

(po 2026-11-02: folded: items 1 and 2 into E059 tickets 1 and 3 (D9), item 3 into E060 ticket 2.)
