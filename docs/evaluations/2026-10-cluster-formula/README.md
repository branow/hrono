# Cluster formula: which similarity puts a service's code together

Run 2026-10-11 on the `bcreg` corpus (`../2026-10-bc-registries/`: lear,
sbc-pay, sbc-auth and business-filings-ui, 8,459 sections in 4,523 files).
It answers backlog epic E050, tickets 501, 502 and 505: core code lands in
leaves with other services' code, tests and build files (E23), one service
is spread over the whole tree (E26), and the top groups do not route (E27).

No model was called. Every formula re-clusters the vectors already stored
for `bcreg` with hrono's own `build_clusters` (UMAP, HDBSCAN leaf, noise
attach), so a formula costs one to two minutes of CPU.

## Decision

Use

```
sim(a, b) = 0.6 · cos(condensed text) + 0.4 · prefix_h(a, b)

prefix_h(a, b) = Σ_{shared leading folders d} 1/d
                 ─────────────────────────────────────
                 sqrt(Σ_{d ≤ depth a} 1/d · Σ_{d ≤ depth b} 1/d)
```

for the leaves, and the same formula one level up: a leaf is the mean of its
members' vectors. The path is the repository name, then the folders, then
the file name. Depth 1 is the repository, so the repository and the service
folder weigh most and deep package folders weigh little. There is no depth
cut and no number tuned to this corpus.

On the mean of three UMAP seeds, against today's formula with the same
grouping:

| | today | chosen |
|---|---|---|
| one-service leaves | 0.84 | 0.90 |
| a service in its biggest group | 0.47 | 0.60 |
| files of one fact sharing a leaf | 0.27 | 0.39 |
| files of one fact sharing a group | 0.66 | 0.76 |
| groups an answer spans (median) | 4 | 2.8 |
| files with several sections split over leaves | 68% | 52% |

**Embedding model: granite** (`ibm-granite/granite-embedding-97m-multilingual-r2`),
not today's MiniLM, which reads only the first 256 tokens: 70% of raw
sections are longer (median 477), so MiniLM clusters code by its licence
header and imports. The scores above were measured with MiniLM over the
stored condensations. In a 32-text pilot (`harness/embed_pilot.py`) the
E23 listener was nearer its own flow than the tests it had been clustered
with in 33% of cases with MiniLM, 33% with bge-base, 50% with nomic and
100% with granite; on condensed text every model got it right. Granite on
the whole corpus is the rebuild's to show.

The formula that scored best overall, `cond3-x7-d4` (0.996 one-service
leaves, 0.40 fact files in one leaf), counts only the first 4 path segments.
That 4 fits this corpus's `repo/service/src/package` layout and would need
retuning on another, so it was not chosen.

## What each term does

- **Content, raw or condensed.** Today hrono embeds the raw section text.
  Licence headers, imports and test idioms then make files of different
  services look alike. The embedding of the section's condensation (the text
  condense already writes) groups behaviour better: on its own it is worse
  than raw text (0.62 against 0.67 one-service leaves), but mixed with a
  folder term it is clearly better (0.39 against 0.32 fact files in one
  leaf).
- **Path embedding (today's second term).** MiniLM over the path string. It
  sees `entity-pay/.../worker.py` and `tests/.../test_worker.py` as close
  strings, and the path does not include the repository. Adding the
  repository name did not help (`repo-path`). The chosen formula drops it.
- **Shared leading folders.** Two sections share the folders from the left
  of their paths. Counting every folder equally (`prefix`) gives the purest
  leaves (0.99) but splits one behaviour by layer: `models/`, `services/`
  and `resources/` land in different leaves, and fact files in one leaf drop
  to 0.18–0.21. Weighting folders by 1/d keeps services apart and lets the
  content decide inside a package.
- **Grouping with the same formula (`+g`).** hrono groups leaves today on
  their briefs' content only. Carrying the folder term up raises "a service
  in its biggest group" from about 0.39 to 0.47–0.61 for every formula. A
  brief then needs a path vector: the mean of its members'.

## How it was measured

The reference labels come from path rules, written as data in
`harness/labels.py`, and are used only to score:

- **Component:** the nearest folder with a build file (`setup.py`,
  `pyproject.toml`, `package.json`, `Dockerfile`), for example
  `sbc-pay/pay-api` or `lear/queue_services/entity-filer`. 67 components.
- **Kind:** code, test, fixture, build, docs or migration.

The ground truth for "what belongs together" is the 36 architecture
questions of `../2026-10-bc-registries-agents/data/arch.json`. Each fact
there names the files that do one thing together.

| metric | meaning |
|---|---|
| one-service leaves | share of sections whose leaf's most common component is theirs |
| service in its biggest group | share of a component (≥ 20 sections) in its biggest level-1 group |
| fact files share a leaf / group | of all pairs of files one fact cites, the share whose leaves (groups) meet |
| groups per answer | median, over the 36 questions, of the groups the answer files sit in |
| split files | files with several sections whose sections sit in more than one leaf |

Level 1 is a proxy: hrono clusters the briefs' embeddings, which need LLM
calls. Here a leaf is the mean of its members' vectors. On today's real
leaves the proxy gives 5 groups per answer and the real tree 6, so it is
close.

The harness reproduces the real tree: today's formula re-clustered gives
the same component purity (0.838) as the tree hrono built.

## Results

All 28 formulas on three seeds are in [data/results.md](data/results.md).
Sorted by "fact files share a leaf", the ones that matter:

| formula | one-service leaves | service in its biggest group | fact files share a leaf | split files |
|---|---|---|---|---|
| `cond3-x7-d4+g` (cond 0.3, first 4 segments 0.7) | 0.996 | 0.61 | 0.40 | 40% |
| `cond6-h4+g` (cond 0.6, 1/d folders 0.4), **chosen** | 0.90 | 0.60 | 0.39 | 52% |
| `cond5-e5+g` (cond 0.5, 0.6^d folders 0.5) | 0.93 | 0.61 | 0.34 | 52% |
| `cond5-h5+g` (cond 0.5, 1/d folders 0.5) | 0.93 | 0.60 | 0.34 | 45% |
| `c3-x7-d4+g` (raw 0.3, first 4 segments 0.7) | 0.99 | 0.59 | 0.33 | 59% |
| `c5-h5+g` (raw 0.5, 1/d folders 0.5) | 0.92 | 0.56 | 0.32 | 72% |
| `current+g` (today, grouped with the same formula) | 0.84 | 0.47 | 0.27 | 68% |
| `cond-only+g` (condensed text alone) | 0.62 | 0.38 | 0.27 | 82% |
| `c3-x7+g` (raw 0.3, all folders equal 0.7) | 0.99 | 0.57 | 0.21 | 33% |

The chosen formula varies more between seeds than the capped one: fact
files in one leaf were 0.43, 0.40 and 0.34.

### The two traced questions

`data/detail/<formula>/questions.md` lists, per question, every answer file
with its leaves and groups; `leaves.md` lists every leaf with its main
component, kinds and files. For `lear-filings-1` (E23), today and with a
folder term:

| file | today's leaf | with a folder term |
|---|---|---|
| `entity_pay/worker.py` | 35% `queue_services/common`, with test helpers | entity-pay only |
| `entity_filer/worker.py` | split: `queue_services/common` and entity-filer | entity-filer only |
| `models/filing.py` | 3 leaves | 1–2 legal-api leaves |
| `file_future_effective.py` | a leaf led by involuntary-dissolutions | still with the other small `lear/jobs/*` services |

Small services under one folder (the `lear/jobs/*` jobs) still share a leaf:
each has fewer sections than a leaf needs.

"With a folder term" is the capped `cond3-x7-d4`. The chosen uncapped
`cond6-h4` does **not** fix the first row with MiniLM: on seed 42
`entity_pay/worker.py` stays in a test-helpers leaf. It was chosen anyway
for having no corpus-tuned depth, with granite expected to close the gap;
E23 is to be checked again on the rebuilt tree.

## What it does not solve

- **The briefs.** E24, E25 and E28 (no flow stated, file catalogs, bare
  name lists) are about what the briefs say. That is the condense and brief
  prompts' work.
- **Pipeline order.** Clustering on condensed text means condense runs
  before clustering. `maintain` already condenses before it clusters; on
  an update, a changed section needs its condensation (one cheap model call)
  before it can be placed.
- **Upper levels.** The "+g" scores group leaves by the mean of their
  members' vectors. hrono groups by the embedding of each leaf's brief;
  the rebuild keeps that and relies on the new briefs.

## Reproduce

```
cd harness
uv run python load.py ~/hrono-eval/db/hrono.db ~/hrono-eval/mirror $S/corpus.npz
uv run python embed_condensed.py ~/hrono-eval/db/hrono.db $S/corpus.npz $S/corpus.condensed.npy
UMAP_SEED=42 uv run python run.py $S/corpus.npz \
  ../../2026-10-bc-registries-agents/data/arch.json $S/seed42 [formula ...]
python table.py ../data > ../data/results.md
```

`run.py` holds every formula as data (`VARIANTS`). `data/detail/` keeps the
per-leaf and per-question traces of the real tree, today's formula and the
three candidates, from seed 42, plus each one's `assignment.npz`.
