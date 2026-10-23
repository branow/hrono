# Handoff: hrono vs code only on BC Registries (state on 2026-10-23)

Read this first, then `README.md` (every round, newest at the bottom).

## The goal

On hard architecture questions over the BC Registries corpus, agents that use
the hrono tree should clearly beat agents that only read the code (target
about 0.9). Today they don't: hrono 0.65-0.67, code only 0.63, on 15
questions with 2 tries each.

## Where everything is

| what | where |
|---|---|
| rounds, results, findings | `README.md` (this folder) |
| harness (agent runs, rebuild, recall) | `harness/` here; `agent_v2.py`, `subtree_v9.py`, `recall_cache.py`, `recall_bin.py`, `rescore.py` |
| launch scripts (rebuild, test, recall test) | `harness/launch/` (copies; they run from `~/hrono-eval/`) |
| `run_agent` (the `claude -p` wrapper) and `steps.py` | `../2026-10-bc-registries-agents/harness/` |
| scoring (Opus judge) | `~/hrono-deep/harness/score.py hard15 <arm>...` |
| questions and reference facts | `~/hrono-deep/data/hard15.json` (5 facts audited, `hard15.before-audit.json` is the old one) |
| corpus (the code) | `~/hrono-deep/corpus/` |
| answers and scores per arm | `~/hrono-deep/runs/hard15-<arm>.jsonl`, `.scores.jsonl` |
| full agent traces (from 2026-10-23 on) | `~/hrono-deep/runs/traces/*.jsonl`; render with `python3 ../2026-10-bc-registries-agents/harness/steps.py <trace>` |
| run logs | `~/hrono-eval/*.log` |
| the tree (db) | `~/hrono-eval/db/hrono-v9.db` (current, full rebuild); `hrono-v15..v18.db` are earlier rounds |
| the export agents read | `~/hrono-eval/export-bcreg-v9-L3/` |
| disputed claims checked against code | `claims/verdicts*.json` |

Arms: `hrono-full{a,b}` (map, full rebuild), `code-full{a,b}` (`MAP=none`),
`hrono-rec{a,b}` (map + recall attached, turn rules), `hrono-v14..v18{a-d}`
(the two tuned questions only, earlier trees). `hrono-trace1` is one traced
run of failure-1.

Run one agent:
`cd harness && MAP=plugin RECALL=1 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run <qid> <arm>@sonnet`
(`MAP=none` for code only). Score: `cd ~/hrono-deep && uv run --project ~/repos/hrono python harness/score.py hard15 <arm>@sonnet`.

## Rules the user set

- Spend nothing without asking; pilot with a few calls first. Each agent run
  costs about $0.3-0.7; a full 15 x 2 test about $14-18.
- Analyze existing logs and artifacts first; fix every found fault before a
  new run.
- No Sonnet for condensing (cost); condense is Haiku, briefs are Sonnet.
- Use glossary words: section, condensation, brief, upper brief (never "area
  brief", "pages", "notes").
- Short, plain answers.
- Never read `serve*.log`, `home*/config.toml`, db rows with secrets,
  `sbc-pay/pay-api/src/pay_api/config.py` or the export brief 796: the
  secrets canary blocks them.

## Open findings (2026-10-23, not yet acted on)

- The tuned questions still win (failure-1 0.64 vs 0.50, legacy-0 0.81 vs
  0.69), less than in rounds 14-18 because the old code-only baseline (two
  runs, 0.29/0.43 on failure-1) was low; fresh code-only runs scored
  0.43/0.57.
- failure-1 fell 0.79 -> 0.64 on one fact (#4, the legacy NATS entity-pay
  worker processes a second delivery again): the fact is in leaf brief 797,
  but after the full rebuild 797 sits under the EFT upper brief (458), and
  neither 458's text nor the filing-pipeline upper brief (459) mentions it;
  no full-rebuild run opened it. A full rewrite of upper briefs drops
  pointers by chance.
- Agents in the full-rebuild runs read the overview and 2-3 upper briefs,
  then switch to shell `cat`/`grep`/`sed` on briefs (17 of 21 calls in one
  run). Before 2026-10-23 only call inputs were logged, not results.
- The traced run (`hrono-trace1`, $0.66): recall led it to 797 at step 2;
  steps 12-19 were eight greps hunting the stale-payment repair; it never
  opened the emailer brief (fact 5).
- hrono's answers carry fewer wrong statements than code only (26 vs 37), not
  more facts. Brief sizes: median 14 KB, 31 over 30 KB (topic 556 is 54 KB).
