# Export evaluation

Does an agent find things in an export faster than in the raw repository? This
measures it: headless Claude Code answers the questions in `questions.toml`
over each folder it is given, and `run.py` writes a report of what it read,
what it spent and whether it was right.

It is run by hand. Every question is one agent session per folder, billed
through your Claude Code login, so 22 questions over four folders is 88
sessions. The gate never runs it; `tests/eval/` pins its grading without an
agent.

## Run it

You need a built tree of hrono's own repository (the question set is about
it), scoped the way `questions.toml` says, and `claude` on your PATH.

```sh
OUT=dev/eval/runs/$(date +%F)
for n in 2 3 4; do hrono tree export default --levels $n -o $OUT/levels-$n; done
mkdir -p $OUT/raw && git archive <commit the tree was built from> \
  src README.md CONTRIBUTING.md GLOSSARY.md pyproject.toml | tar -x -C $OUT/raw

uv run python dev/eval/run.py --out $OUT \
  --operator-mark <a word your ~/.claude/CLAUDE.md carries> \
  --arm levels-2=$OUT/levels-2 --arm levels-3=$OUT/levels-3 \
  --arm levels-4=$OUT/levels-4 --arm raw=$OUT/raw
```

The raw folder is the baseline: the same files the tree ingested, at the same
commit, so both sides of the comparison hold the same facts. A folder with a
`root.md` is treated as an export, anything else as raw.

`--tools Read,Glob` takes Grep away, so the agent has nothing to do but walk the
folder: that measures the export's navigation rather than its searchability.
`--only q01,q05` runs a subset (an id the question set does not have stops the
run, naming it), `--model` picks the agent (default `sonnet`), `--jobs` how many
sessions run at once (default 4). `--rerender` grades and reports the sessions
already recorded under `--out` again without running any, so a corrected
question or grading rule costs nothing to apply; with `--only` or fewer `--arm`s
it reports just that subset, and it stops, naming the pair, if one asked for was
never recorded. `--operator-mark` is described under Isolation.

## What it writes

Under `--out`: `report.md`, `runs.jsonl` (one record per session, appended
as each finishes, so a run interrupted part way keeps what it paid for and
`--rerender` reports it),
`isolation.json` (the probe's replies) and
`transcripts/<arm>/<question>.jsonl`, the raw stream of every session.

The report has a totals row per folder, a row per question per folder with
the pages it opened in order, and the full path every failed question took.
Two hop limits over a tree already within the smaller one export the same
folder; the report names such twins, and whatever differs between them is the
agent's own run-to-run variance. Per session it counts:

- **reads** — `Read` calls on files in the folder, in order. Glob and Grep are
  allowed in every arm and listed under tools, so a folder that is searched
  rather than walked shows as few reads and many tools.
- **reads to settler** — the read that first opened the file that settles the
  question (in an export, a section page headed by that file's path). The
  fewer, the faster the folder led the agent there.
- **depth** — directories between the folder's root and that page.
- **correct** — the ANSWER line contains an expected word AND a SOURCE line
  names a settling file. A no-answer control is correct only when the agent
  says NOT FOUND and cites nothing.
- **tokens** — input, cache creation, cache read and output, as the CLI
  reports them; **cost** is the CLI's own `total_cost_usd`.

A session that times out (15 minutes) or prints a line that is not valid JSON
is recorded as a failed question with the reason under "session ended", and
keeps whatever it read before; a session that raises is recorded the same way
with the exception as its reason, and the other sessions are unaffected.

## Isolation

The review found the operator's `~/.claude/CLAUDE.md` reaching model calls
(#217). Each session therefore runs in a fresh temporary copy of the folder,
outside any repository, with `--safe-mode --restricted --strict-mcp-config
--no-session-persistence`, only Read/Glob/Grep, a replaced system prompt, and
none of the calling session's `CLAUDE_CODE_*` variables.

Before any question runs, a probe plants a CLAUDE.md naming a canary above the
working directory and asks two sessions to list what their instructions
mention: one without the flags (it must quote the canary, or the probe proves
nothing) and one with them (it must not quote it). That proves project memory
is kept out. To prove the same for user memory, pass
`--operator-mark <word>`, a distinctive word your own `~/.claude/CLAUDE.md`
carries (a skill name, say): the control must quote it too and the isolated
session must not. Without the flag the report says user memory was not tested.

The probe also fails when the isolated reply quotes the harness's user context,
a `userEmail` entry or an email address. The CLI has no flag that drops it (the
account email is injected even under `--safe-mode`), so an isolated session may
still see it: the probe is then NOT verified and the run stops unless
`--allow-unisolated` is given. Either way the report, `isolation.json` and
the isolation report printed to stderr on a failed probe have every email
address replaced by `[email redacted]` before they are written or
printed.
Injected context that is not email-shaped, such as a company name, is neither
probed nor redacted.
If the probe fails the run stops before spending anything else; the report
prints both replies.

## The question set

Each question names the file that settles it and the words a right answer
contains. `shallow` questions are facts a top-level brief should surface,
`deep` ones are constants or rules several hops down, and `none` questions are
controls the corpus cannot answer. Facts were settled against main at f3e4853;
when the code they cite moves, `tests/eval` fails on a settling file that no
longer exists, and a changed value needs the question updated by hand.
