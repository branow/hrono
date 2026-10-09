# hrono admin panel — requirements (reviewed 2026-10-03)

One line per requirement: what the user must be able to do or see.

Status tags, from reading the current code (not from clicking through the UI):

- `[have]` — exists today
- `[partial]` — exists but incomplete or awkward; the note says what is missing
- `[missing]` — not in the panel (may exist in the CLI/API)
- `[suggest]` — my proposal, not in the spec
- `(optional)` — nice to have, not needed for a comfortable first version
- `[skip]` — decided out of scope for now
- `-> E0NN` — the board epic (`.autodev/board/`) that delivers it

## Who uses it

- **Admin** — sets hrono up, pays for the LLM calls, manages access.
- **Curator** (writer) — keeps the tree correct: reviews, fixes, re-runs.
- **Reader** — browses the tree, searches and asks questions, changes nothing. A real audience, not an afterthought.

## 1. Getting in

1. `[have]` Sign in with a token; see only what my role allows.
2. `[have]` Switch between trees from any page.
3. `[have]` Pick light or dark theme.
4. `[have]` Admin: list users, create a user/token, revoke one, change a role. (E012)
5. `[have]` Admin: rotate the master key from the panel. (optional) (E012)
6. `[have]` See who I am signed in as and my role on every page. (name + role chip in the shell, base.html; po 2026-10-04)

## 2. First-time setup

7. `[have]` Be walked from an empty install to a built tree without the CLI. (E013; hardening -> E026)
8. `[have]` Add a connection (provider + API key) through a form, and test that it works before saving. (E013)
9. `[have]` Assign a model to each pipeline role (condense, brief, brief-upper, judge, embedding).
10. `[have]` Add a source (git URL, auth, branch, path filter) through a form. (E006)
11. `[have]` Preview which files a source filter keeps before paying for anything. (E013)
12. `[have]` See an estimate of calls, cost and time before starting a first build. (E013)
13. `[have]` Start the first build with one button and watch it run.

## 3. Understanding the state at a glance (home page)

14. `[have]` See the tree's size: topics, levels, sections filed, sections waiting.
15. `[have]` See what needs attention, each item linking to where it is fixed.
16. `[have]` See recent runs and their outcome.
17. `[have]` See per source: last sync time, the commit it is at, and whether it is behind. (E005)
18. `[have]` See a running job's progress on the home page, not only on the runs page. (E005)
19. `[have]` See total spend (tokens and cost) on the home page: last run and all time. (E008)
20. `[have]` See when the tree was last fully up to date, in one sentence. (E005)

## 4. Browsing the knowledge

21. `[have]` See the tree as a map; pan, expand and collapse topics.
22. `[have]` Click a topic and read its brief in a side panel without leaving the map.
23. `[have]` Open a topic page: brief, children, member sections, condensations, provenance.
24. `[have]` Read a section's actual source text.
25. `[have]` Browse the tree as a plain outline/list, as an alternative to the map. -> E011 (ec0bcfb)
26. `[have]` Search topics and sections by text and jump to the result. -> E011 (ec0bcfb)
27. `[have]` Go from a file path to its sections and the topic that holds them. -> E011 (ec0bcfb)
28. `[have]` See where I am in the tree (breadcrumb to root) on every topic page. (E010)
29. `[have]` Link from a section to its file in the source repository. -> E039
30. `[have]` Share any view by copying its URL.

## 5. Asking questions (recall) — confirmed: the panel is a place to ask, for every role -> #207

31. `[have]` Type a question and see exactly what recall would inject for an agent.
32. `[have]` See each returned passage's source, score and the topic it belongs to.
33. `[have]` See clearly when recall found nothing confident, and which topics to explore instead.
34. `[have]` Keep a short history of questions tried, to compare before and after a fix. -> E040

## 6. Keeping it up to date

35. `[have]` Sync a tree with one button.
36. `[have]` Run any single pipeline step manually, with a plain explanation of what it does.
37. `[have]` Watch a run live: status, progress, sub-steps, spend.
38. `[have]` Cancel a running job.
39. `[have]` Read why a run failed in plain words and what to do next — stage, sentence, remedy (#213); a failed run says it stopped before it finished (E002).
40. `[have]` Retry a failed run with one click. (#213, E002)
41. `[skip]` Schedule automatic sync — everything runs manually for now.
42. `[skip]` Trigger sync from a git webhook.
43. `[have]` See the activity log: what each sync changed and what the judge decided.
44. `[have]` See a per-run summary of "what changed in the tree" (topics added, moved, rewritten). (#213; per-stage counts and failed runs honest, E002)

## 7. Health and review

45. `[have]` See all health checks in one list: unreachable, missing brief, waiting, forced, failed.
46. `[have]` See health on the map itself (overlays: misfit pull, proximity, propagation).
47. `[have]` Fix each health item from where it is shown. -> E009 (421a0df)
48. `[have]` See which briefs are stale and regenerate one topic's brief on demand. -> E009 (421a0df)
49. `[have]` See the waiting (parked) sections and place one into a topic by hand. -> E009 (421a0df)
50. `[have]` Each health item says whether automation will fix it or a person must. -> E009 (421a0df)

## 8. Correcting the tree by hand

51. `[have]` Rename a topic.
52. `[have]` Rewrite a brief, and have the edit survive later runs (pin).
53. `[have]` Release a pin so automation takes over again.
54. `[have]` Add a note to a topic.
55. `[have]` Move a topic under another parent.
56. `[have]` Merge two topics, split one, or dissolve one.
57. `[have]` Move a section to another topic.
58. `[have]` Be asked to confirm destructive edits, with what will change stated first. (E010)
59. `[have]` See which topics are pinned / hand-edited, across the whole tree. -> E009 (421a0df)
60. `[have]` See a brief's previous versions and what changed. (optional) -> E033
61. `[have]` Undo the last manual edit. (optional) -> E034
62. `[have]` See who made each manual edit and when. -> E039

## 9. Configuration

63. `[have]` View and edit connections, models, prompts, sources and trees.
64. `[have]` Secrets are never shown back after saving.
65. `[have]` Before saving a change, see what it invalidates and what re-running will cost. (E006)
66. `[have]` Get field-level validation errors in the form. (E006)
67. `[have]` Create a new tree and choose its sources through a guided form. (E006)
68. `[have]` Edit a prompt and preview the result on one topic before applying it to all. -> E043
69. `[have]` See server settings that are set by environment (LLM concurrency, version, DB path) read-only. (E006)

## 10. Export — the tree as files an agent reads (milestone)

The CLI and API already export (`hrono tree export`, 4 levels by default, by keeping evenly spaced stored levels). What is missing is control over the shape, the panel, and proof that an agent can use the result.

70. `[have]` Export a tree to a folder of Markdown files — works from the CLI only.
81. `[have]` However deep the stored tree is (20-30 levels), the export is at most 3-4 hops from root to a section — today levels are dropped evenly, with no control over what that does to width.
82. `[have]` Compaction makes levels wider but keeps every index page readable: no page lists more children than an agent can scan.
83. `[have]` Choose the hop limit when exporting, from the CLI and the panel, with the same options and the same result.
84. `[have]` Preview the export's shape (levels, pages per level, widest page, file count) before producing it.
85. `[have]` Download the export from the panel as one archive.
86. `[have]` Prove it works: a real agent answers real questions from the exported folder, and hops, files read and correctness are recorded. -> E004
71. `[have]` Copy a ready snippet for connecting an agent (CLI profile / API call / export path) to this tree. -> E041
72. `[have]` See how often agents call recall and what they ask. -> E042

## 11. Cost and usage — confirmed: in the first version

Everything below reads from one record kept per model call, tied to the run that made it. Store per call; show any roll-up.

87. `[have]` Every model call is recorded with its run, the user who started the run, the configured model, the actual upstream model, the provider, tokens in/out (cache tokens included) and how long it took.
88. `[have]` See tokens, cost and model time per run, on the run's page. (E008)
89. `[have]` See tokens, cost and model time per model — the configured one and the actual upstream one. (E008)
90. `[have]` See which runs cost the most, and which user started them. (E008)
91. `[have]` Cost is honest about the backend: a per-token price for API providers, "covered by subscription" (with the API-equivalent figure shown as an estimate) for `claude-code`.
92. `[have]` See total hours of model execution per model. (E008)
93. `[have]` The same numbers from the CLI (`hrono usage`).

## 12. Across every page (UX)

73. `[have]` Every term has a short hint next to it, and a guide page explains the vocabulary with this install's numbers.
74. `[have]` Every action reports what it did, in plain words, on the page I am on. (E005)
75. `[have]` Every empty state says what to do next, with a button rather than a CLI command. (E005)
94. `[have]` Nothing overlaps, clips or is mislabelled: every finding of the 2026-10-03 UI review, recorded in the tickets, is closed out. (E005, E006, E007, E010, E014)
95. `[have]` A topic has a name a person can tell apart from its neighbours — today seven topics are called `src/click` or `docs`.
96. `[have]` A brief that is model chatter or a refusal is never stored as a good brief. — briefs and condensations gated at any size and length (E001, E015).
76. `[have]` Long lists (runs, sections, activity) can be filtered, sorted and paged. (E002, E010, E024)
77. `[have]` Live data refreshes without reloading on every page that shows running work. (E005)
78. `[have]` One consistent navigation: Home, Map, Ask, Runs, Health, Usage, Export, Settings, Guide. (E005)
79. `[have]` Works on a laptop-width screen without horizontal scrolling — every page overflows by 4px today, the home page by 22px at 800px. (optional: mobile) (E005)
80. `[have]` Keyboard access for the map and the main actions. -> E044

## Decisions (2026-10-03)

- Reader is a real role: read the tree, traverse it, search and ask.
- Recall is available in the panel.
- Cost visibility is in: stored per call per run, shown per run, per model and per user.
- Scheduling and webhooks are skipped for now.
- Export compaction to 3-4 hops, from both CLI and panel, tested with real agents, is its own milestone.
- The existing interface gets a review-and-fix pass.
