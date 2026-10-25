# Evaluation: hrono on xgboost (October 2026)

A cold build of one tree over the xgboost repository, the corpus a paper
uses to evaluate question types against hrono. This folder keeps how the tree
was built and what the build cost, so the questions run later sit on a known
tree.

## Corpus

`github.com/dmlc/xgboost`, pinned at `7f2e1f2242f8f0500cf4e22fab7a7ab4ee302120`
(2026-10-23, "[mt] Replace the custom grad reduction with random projection.
(#12736)"). 1,457 tracked files: `src/` 415, `tests/` 334, `jvm-packages/`
142, `R-package/` 132, `doc/` 93, `demo/` 88, `ops/` 66, `python-package/`
62, the rest under 40 each. The `dmlc-core` submodule is not followed.

## Setup

Everything lives outside the repository in `~/hrono-xgboost`:

| Path | What it is |
|---|---|
| `upstream/xgboost` | Full clone from GitHub. |
| `mirror/xgboost.git` | Bare clone at the pinned commit; the git source points here by absolute path, so the tree never moves unless the mirror does. |
| `db/hrono.db` | The database: tree `xgboost`. |
| `hrono.key` | The master key. |
| `home/`, `token` | CLI profile `xgb` and its admin token, used through `scripts/h`. |
| `serve.log`, `build.start`, `build.job`, `watch.log` | Server log, start time and id of the cold build. |

hrono at `9b8fcb3`, `hrono serve --port 8790 --key-file hrono.key --db
db/hrono.db` under `nohup`, `HRONO_LLM_CONCURRENCY=6`.

| Registry item | Config |
|---|---|
| connection `claude` | provider `claude-code` (the operator's Claude subscription) |
| model `emb` | `sentence-transformers/all-MiniLM-L6-v2`, in-process |
| model `condense` | `haiku` via `claude`, role `condense` |
| model `brief` | `sonnet` via `claude`, role `brief` |
| model `brief-upper` | `sonnet` via `claude`, role `brief-upper` |
| model `judge` | `haiku` via `claude`, role `judge` |
| source `xgboost` | `git`, `~/hrono-xgboost/mirror/xgboost.git`, no filter |
| tree `xgboost` | sources `["xgboost"]` |

The same model split as the BC Registries build
(`../2026-10-bc-registries/`).

## Log

- 2026-10-25 12:05 UTC+3: `hrono tree maintain xgboost`, job
  `job_f80c65eb5eef4c2580f7e6b0ee445524`. Split: 1,442 files, 2,245
  sections, 0.3 s fetch, 12.8 s split.
- 13:21: the build succeeded in 1 h 16 min wall clock. 0 pending
  sections, health clean (0 waiting, 0 misfits, 0 stale).

  | Stage | Seconds | Result |
  |---|---|---|
  | embed | 102 | 22,319 passages |
  | condense | 3,034 | 2,237 of 2,245 sections |
  | embed-condensations | 15 | 2,234 |
  | cluster | 25 | 139 leaf topics (18 split, 593 sections attached) |
  | brief | 1,299 | 139 leaf briefs |
  | build-tree | 97 | 7 level-1 topics, 1 root (8 `brief-upper` calls) |

  Usage (`hrono usage`; subscription, the API-equivalent price is an
  estimate, not money spent): condense 396 calls, 4.27 h model time, $14.76;
  brief 140 calls, 1.79 h, $16.08; brief-upper 9 calls, 3.9 min, $3.11;
  judge 1 call. About $34 API-equivalent in all.

## Notes

- **The root brief is wrong.** The root (node 162, level 2) has seven
  children and its `brief-upper` call got all seven (23k input tokens), yet
  the brief it wrote is a near-copy of its first child's, node 155, the
  static demo data ("Static demo and test data with data-preparation
  scripts"). `export/root.md` therefore opens with the wrong subject. No
  gate caught it. Not fixed: there is no route to rewrite one brief except a
  manual override, which pins it.
- Level-1 briefs 155 and 161 have no `#` heading line; the other five do.

- README's quickstart shows `hrono connections set <name> -f -`; the CLI
  rejects `-f -` ("File '-' does not exist"). Omit `-f` to read stdin.
