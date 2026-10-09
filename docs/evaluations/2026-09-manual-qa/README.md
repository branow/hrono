# Evaluation: end-to-end manual QA (September 2026)

The first time hrono was driven end to end by hand, on 2026-09-03, against a
few small real repositories, once milestones M0–M7 were in place. Every stage
was run through the server and the API, and each failure was recorded as a
numbered finding. These findings are the F-numbers that commits and
`CONTRIBUTING.md` cite (F5, F21, ...).

- `findings.md`: F1–F14 from the run, then F15–F18, which the same run found
  in the clustering recipe at small sizes. Each has a severity, evidence and
  its fix. Evidence paths are relative to the run's working folder, which was
  not kept.
- `reports/`: the measurements the findings rest on: index integrity, ingest
  coverage, section reassembly, recall before and after briefs, the
  UMAP-threshold sweep, update and propagate scenarios.
- `scripts/`: the harness the run used: `api.sh` (curl with the run's
  token), `enqueue.py`/`run_op.sh` (start an op as a job), `inspect_tree.py`,
  `dbstat.py`, `verify_reassembly.py`, and a `claude` CLI proxy that
  recorded every call.

Not kept: the run's databases, cloned repositories, recorded LLM calls and
logs (about 46 MB, all reproducible), and the run log, which contains a live
server token.
