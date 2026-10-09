# E007 Guide audit: claim -> code -> verdict

| claim | backing code | verdict |
|---|---|---|
| Change a model in Settings and every brief it wrote goes stale | summarize/briefs.py `_is_fresh` (name, upstream model, params, prompt hash); summarize/store.py `pending` keys condensations by model name only; registry/impact.py preview | FALSE as written. Now: brief/brief-upper model or prompt edits rewrite briefs at the next brief run; connection changes rewrite nothing; condensations survive an upstream edit |
| Judge is asked per level and the rewrite stops at the first level that says no | summarize/propagate.py `_judge`, `_climb` | FALSE. One panel (BEST_OF) per changed leaf; a non-none verdict marks every ancestor up to D_MAX. Rewritten |
| Propagation arc runs up to the highest brief the judge said no longer held | propagate `_climb`, update_log climbed_to | Reworded: highest brief marked for rewrite |
| "the whole tree drifting: a full warm rebuild" listed under what it fixes by itself | tree/sync_chain.py (settle deliberately not in chain); tree/settle.py `should_settle` | FALSE. Settle is operator-started; sync only reports it is due. Moved out of the rules list with CHURN_THRESHOLD and MISFIT_FACTOR |
| A freshly built tree measures around 3% | no constant; monitor.baseline records the first measure | Unsupported number removed |
| Edited file: sticky re-check at TAU, else re-placed | cluster/placement.py `_sticky` | true |
| New file: nearest centre >= TAU else parked | placement `assign_or_park` | true |
| Parked sections form a topic once enough gather | cluster/incubator.py `drain`, MIN_POINTS | true; added MAX_AGE force-assign rule (incubator.age) |
| Renamed file keeps its topic | placement `_in_place` | added, true |
| Topic past MAX_CAP splits; over MISFIT_THRESHOLD sheds; below two dissolves | cluster/repair.py `repair` | true |
| Cap is the summarization budget | repair.MAX_CAP comment | true |
| Cached by content hash, unchanged file never condensed twice | summarize/store.py `pending` | true; caption sits under condensation |
| Re-run over unchanged sources makes zero model calls | tree/update.py docstring, E015 | true except stored talk-backs, now stated |
| Flagged brief kept rather than dropped | summarize/briefs.py `unusable`, node page Flagged | true |
| Hand edit is pinned | pins.py KINDS brief/membership/parenting | narrowed: three kinds; renames and notes persist separately |
| Fit number is closeness to the centre | server/templates/node.html fit chip | true; forced has none |
| A tree is a name plus its sources; many per database | registry/collections/trees.py | true |
| Overlays: pull/proximity/propagation | server/overlays.py | true; label said "chunks" (fixed) |
| Roles: reader/writer/admin abilities | Reader/Writer/Admin dependencies; registry write_role; tests make a request per role | new section, held by test |
| Recall: confidence floor, cap, per-document share, refusal message | recall/vector_leg.py, fusion.py CAP, MAX_DOCUMENT_SHARE, EXPLORE_MESSAGE | new section, numbers from constants |
| Export: root.md, hop limit, page width | export/collapse.py WIDTH, ui/export.py DEFAULT_LEVELS | new section |
| Cost: only model calls cost; judge panel per changed topic | propagate BEST_OF, usage/rollup.py | new section |
| ~10 KB section, ~800 B passage | ingest/split/constants.py | now from constants via `limits` |
| 0.7 / 30 / 25% | placement.TAU, repair.MAX_CAP, MISFIT_THRESHOLD | already constants; test moves every figure and the page follows |
