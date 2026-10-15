# Glossary

The words hrono uses, and the ones it deliberately does not. The dashboard
uses only these words, and a test fails on any word listed under
[Words we do not use](#words-we-do-not-use). See
[docs/architecture.md](docs/architecture.md) and
[docs/summarization.md](docs/summarization.md) for how the pieces fit.

## The shape of what hrono builds

**source** — a place hrono reads: a git repository (`git`), every repository
of a GitHub user or organization (`github-user`), every repository of a
Bitbucket workspace (`bitbucket-workspace`), Confluence pages chosen by space
or page (`confluence`), or the Notion pages shared with an integration
(`notion`). Registering one pulls nothing; `sync` does.

**section** — the organizing unit. Around 10 KB of one file, filled greedily to
a per-category budget (code 10 KB, docs 10 KB, data 2 KB). A section is what
gets clustered, and what an agent reads when it explores.
*Superseded name: **chunk**; see [Words we do not use](#words-we-do-not-use).*

**passage** — around 800 B, the unit **recall** injects into a prompt. A section
reassembles byte-identically from its passages. Passages exist for retrieval;
sections exist for structure. They are not interchangeable.

**condensation** — what the first LLM pass writes about one section: every
check, branch, error path and call it holds, identifiers copied verbatim. It is
what the brief is written from and is never shown to an agent. Cached by the
section's content hash, so an unchanged file is never condensed twice. This is
the **map** half of map-reduce.

**topic** — a group of related sections, or of other topics, plus a brief. The
node of the tree. Bottom-level topics hold sections; topics above hold topics.

**brief** — an LLM-written summary of what a topic is, written from its
sections' **condensations**, not from their raw text. This is the **reduce**
half. It states what the group is as a whole, surfaces the groupings actually
present rather than an imposed structure, and ends with a `Caution:` section
aggregating the gotchas. Reference lists are appended mechanically by code and
are never written by the model.

**tree** — topics all the way up to a single root, over a named set of sources.
One database can hold several.

## What happens to it

**sync** — bring a tree up to date after its sources changed. The incremental
verb: it touches only what moved.

**maintain** — build a tree that does not exist yet, end to end. The cold verb,
and the expensive one. It refuses a tree nobody registered (`default`
always exists).

**recall** — answer a question by injecting the passages that answer it, with
provenance. Strict on purpose: when nothing clears the confidence floor it says
so and hands over to explore rather than inject something plausible. Each
call an agent makes through the API is logged for the Usage page.

**explore** — the other door: an agent walks the tree itself, reading briefs to
decide where to go.

**job** / **run** — background work. One instruction, which may fan out into
pieces.

## Health and judgement

**stale** — a brief that no longer matches what its topic holds, because the
members changed, or the prompt did, or the model did.

**pin** — a hand edit the pipeline must not undo. Pinning is what makes a
correction survive the next run.

**parked** / **incubator** — a section that is ingested and embedded but in no
topic yet, because the placement rule declined it. It is on the map's waiting
list, not lost.

**misfit** — a section whose own topic's centre is not the nearest one. The
health signal repair and settle act on.

**forced** — a section placed by a rule rather than by a measurement, so it
carries no similarity score.

## Words we do not use

**cluster** — the algorithm's verb. The thing it produces is a **topic**.

**chunk** — an older name for **section**. Do not reintroduce it.

**node** — the internal name for a topic: what the database calls it and what
a URL carries. On screen it is always a topic.

**paragraph** — not a unit in hrono. Splitting is by structure and byte budget,
never by paragraph.

## In Ukrainian

The dashboard also speaks Ukrainian (`src/hrono/server/locales/uk/`). These
are its words for the terms above and for the dashboard's own, chosen to read
naturally and to take about the room the English does. A translation uses
them and nothing else for these ideas.

| English | Українською |
|---|---|
| source | джерело |
| section | фрагмент |
| passage | уривок |
| condensation | конспект |
| topic | тема |
| bottom topic | нижня тема |
| brief | опис |
| tree | дерево |
| root | корінь |
| level | рівень |
| map | мапа |
| sync | оновлення; оновити |
| maintain, build | побудова; побудувати |
| recall | довідка |
| explore | навігація деревом |
| job, run | запуск |
| stale | застарілий |
| pin | закріпити; закріплено |
| parked, waiting | очікує теми; очікують |
| misfit | не на своєму місці |
| forced | примусово |
| hand edit | правка |
| revert, undo | відкотити; скасувати |
| connection | підключення |
| model | модель |
| prompt | промпт |
| token (sign-in) | токен |
| tokens (of a model) | токени |
| reader, writer, admin | читач, редактор, адмін |
| spend | витрати |

The menu: Огляд (Home, Overview), Мапа, Пошук, Зміст (Outline), Запит (Ask),
Довідка (Recall), Демо агента, Запуски, Зміни, Облік (Usage), Стан (Health),
Експорт, Параметри (Settings), Доступ (Access), Тема (Topic), Посібник
(Guide). A run's status: у черзі, триває, готово, помилка, скасовано.

Not used in Ukrainian either: кластер, чанк, вузол (on screen), абзац.
