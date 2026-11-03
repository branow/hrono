# ui-check overlap on a topic page at 1280 (found in E065)
On a long topic (flask node 17) the clamped brief's list items and code spans are reported overlapping the Findings callout and the "Read the whole brief" toggle at 1280, light and dark. Present before E065 (same with the old details rule), likely the clamp's hidden overflow. Check whether it is a false positive or a real overlap.

# qa round 1 (E065)
- ui-check reports overlaps for content of closed disclosures that is not drawn (versions diff on a reviewed topic, outline children, a run's changed tree; 1280 and the outline at 390) since base.html:223 scopes the hide rule to treepick/reveal; teach ui-check to skip elements inside a closed `<details>` (autodev bin/ui-check), or move those disclosures to `hidden="until-found"`.
- `hrono tree review` on a provider error prints only "error: llm-error: the model server returned 500"; print the failed item too ("review of topic 17"), src/hrono/tree/commands.py:104 (watch_job's failure line).
- The run page titles a Review now run "settle - place the sections that were still waiting" (src/hrono/server/ui/jobs.py:73); a settle that only reviewed could say "review the topics that were due".
- `POST /jobs` still queues every other op (brief, brief-upper, ...) for an unregistered tree (src/hrono/server/jobs.py:115); refuse any tree-scoped op the same way.

(po 2026-11-03: left for acceptance 2 to confirm or fold; none blocks O2 or O4. The ui-check item is a fix to the autodev tool, not to hrono.)

(po 2026-11-03, after acceptance 2: the run title and the CLI failure line folded into E066; POST /jobs other ops and the ui-check item stay.)
