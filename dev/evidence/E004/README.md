# E004 evidence: the export, measured

Tree: hrono's own repo at f3e4853, `filter.only` src/** + README, CONTRIBUTING,
GLOSSARY, pyproject (268 sections, 18 topics, 3 stored levels), built on a
scratch server through claude-code (haiku condense, sonnet briefs). Agent:
headless Claude Code sonnet, 22 questions (19 answerable, 3 no-answer).

- `grep/report.md` — tools Read,Glob,Grep; arms levels-2, levels-3, levels-4
  (byte-identical to levels-3), raw.
- `walk/report.md` — tools Read,Glob; arms levels-2, levels-3, raw.

| run | arm | correct | reads to settler | settler reached | tokens | $ |
|---|---|---|---|---|---|---|
| grep | levels-2 | 21/22 | 1.9 | 8/19 | 619,880 | 1.06 |
| grep | levels-3 | 21/22 | 1.8 | 5/19 | 538,647 | 0.97 |
| grep | levels-4 | 20/22 | 2.0 | 5/19 | 547,181 | 0.94 |
| grep | raw | 21/22 | 1.0 | 8/19 | 340,982 | 0.42 |
| walk | levels-2 | 17/22 | 3.2 | 13/19 | 857,498 | 1.54 |
| walk | levels-3 | 15/22 | 2.1 | 12/19 | 765,125 | 1.33 |
| walk | raw | 21/22 | 1.4 | 19/19 | 414,901 | 0.74 |

Isolation verified in both runs (canary quoted by the unisolated control,
absent from the isolated session; the operator's `graphify` likewise).

Findings filed to backlog/: export-costs-more-than-the-raw-repo,
briefs-state-facts-without-their-file,
topic-directories-are-named-by-a-framing-phrase,
hop-limit-3-vs-4-needs-a-deeper-corpus. The claude-code model registration
defect found while building is claude-code-text-model-cannot-be-registered.
