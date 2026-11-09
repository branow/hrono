# How to evaluate hrono

Read this before designing, running or judging any evaluation of hrono.
It records what hrono is for and how a test must be built to measure that.
Agents have repeatedly got this wrong; the points below are settled by the
author (Orest, 2026-11-08) and are not to be re-argued in a run.

## What hrono is for: managing the agent's context

An agent's context is limited. It cannot hold a whole codebase. Left to
itself it greps, reads the few files it finds, and keeps those in context;
everything else in the system it does not know. On a small change that is
enough: any agent can hold five files.

hrono extracts the knowledge of the whole codebase into plain text, once,
and compresses it into a tree: sections -> condensations -> leaf briefs ->
upper briefs -> root. The conventions, rules and flows of the whole system
are already derived there. The agent does not re-read the source again and
again to rediscover them on every task. It reads the summaries for the
system as a whole, and goes to the code only where it implements, for the
fine detail.

So:

- **The map is derived from the code, on purpose.** It is a structured,
  compressed view of the same knowledge, not extra knowledge. "The map
  knows nothing the code doesn't" is not a flaw; it is the design. Other
  sources (threads, Confluence, Notion) can be added, but the core value is
  context management over the code.
- **Rules mined from the code are the right rules to test.** A rule an agent
  could in principle find in the code, but only by reading far more than it
  can hold, is exactly what hrono should give it.

## What a task must look like

- **It needs knowledge of the whole codebase, not of five files.** A change
  whose rules sit in the few files a grep finds will not show hrono; any
  agent holds those. The task must touch many parts of the system, so that
  doing it right needs rules and flows from places the agent would never
  open in its budget.
- **The request is a real BRD, not an implementation plan.** Business people
  write what behaviour they want, in their own domain language, in the
  general case. They do not know file, table, page, utility or repository
  names. Their terms may be loose, wrong or contradict each other. They do
  not mention exceptions, error paths, race conditions, buffers or the
  places the same data reaches. Turning that into the actual rules is the
  agent's job, and the map is what lets it do so.
- **Never write the BRD while holding the checklist.** A BRD written by
  someone who knows the hidden rules leaks them ("orders that recur
  automatically", "however customer details are changed") and turns each
  hidden rule into a stated requirement that code-only can grep for.
  t10-credit-control on webERP did this and code-only met 35.5 of 40.
  Write the BRD first, from the business side only (or take a real one),
  and mine the checklist afterwards.
- **The task statement gives ownership, not a checklist to execute.** The
  agent is the engineer who owns the feature in this system. The BRD tells
  it what the business wants; the agent works out what the full feature
  needs here to make sense and to work (what else must change because it
  depends on it, what the business did not think of) and delivers all of
  it, as a real engineer would. Do not tell it "implement each requirement":
  told to execute a BRD, agents take the minimum path that satisfies the
  text and cut scope (webERP t11: both arms skipped half the feature,
  citing the BRD's open questions). Better context should show as a fuller,
  better-fitting feature, so the agent needs the freedom to show it.
- **Code-only must fail it.** Gate every task with one code-only try first
  (protocol amendment 4). Only a task that code-only gets mostly wrong is
  worth an hrono try.

## How the agent should read the map

The map only helps if the agent reads the right amount of it.

- **Too little:** the agent ignores the map and works from the source by
  grep, which is code-only with extra cost (webERP t4 and t8 try 1: 0 map
  pages read).
- **Too much:** the agent reads every brief, fills its context with
  unrelated knowledge, loses the rules that matter and does worse (webERP
  t10 with "read every brief": 151 pages read, and it still missed rules
  that were on pages it had read).
- **Right:** root.md, the briefs of the areas the request touches, then the
  leaf briefs of the parts it changes or that the same data reaches; code
  only where it implements. The session note, skill, gate and any prompt
  in a test must steer toward this middle, and a test records how many
  pages the agent read so the dose can be judged.

How the agent turns what it read into the change it makes (reading a rule
and still not applying it) is an open problem, recorded in the webERP t10
results.

## How to grade

The mined rules are one part of the grade, never the whole of it. They
can miss what matters, and the map may help in ways no rule list names.
Every comparison also has a reviewer judge the change as a whole: how
complete the feature is, how well it fits the system and its conventions,
how the code is structured, what it would break, what a maintainer would
have to fix, which one it would rather merge and why, and anything good
or bad it noticed beyond the rule list. Report those findings verbatim
next to the rule scores.

## Fairness that still holds

Both arms get the same model, tools, budget and workspace; the hrono arm
adds only the map and the plugin. Protocol and amendments are written
before runs; every run, transcript and score is kept; grading is blind
where arms are compared. A task chosen for the property above is reported
as such, not as an average over all tasks.

## Running experiments

- **Fix before you run.** Fix every known problem in hrono's real code and
  prompts first (not only in the eval harness). After a run, trace where each
  fact was lost (tree, export, agent reading, answer) from the existing
  artifacts and fix every fault found. Propose the next run only when no
  further improvement is visible.
- **Pilot small, state the cost.** Any step that calls a model starts as a
  pilot of about 10 calls or fewer; show the outputs and wait for a go before
  scaling. State the call count and cost before every paid run; anything over
  about $5 needs explicit approval. Free steps (re-clustering stored vectors)
  can run in full. Finish and report one stage before starting the next.
- **The baseline is code-only agents.** Reuse existing code-only runs. Prefer
  agent outcome on one or two questions over proxy judges. Condensations feed
  briefs only; agents never see them.
- **Watch long runs live.** After starting a model-calling job, check within
  2-3 minutes which stages and model roles it runs (`llm_calls` by `job_id`,
  node counts), then about every 10 minutes. Snapshot the db first. Stop it
  the moment it does something other than what was approved.
- **Verify the setup against the best-practice setup.** Before the first paid
  call of an eval, diff the whole registry against this setup, item by item,
  and show the diff (it scored best as of 2026-10-27: the BC Registries full
  rebuild, 0.67 vs code-only 0.63): Haiku for condense and judge, Sonnet for
  brief and upper brief, embedding
  `ibm-granite/granite-embedding-97m-multilingual-r2`, the default prompts
  (compare template hashes), tree `"lookups": true`,
  `HRONO_LLM_CONCURRENCY=6`. hrono's own defaults are not this setup (lookups
  is off by default). Never copy a setup from an older eval's README. Two traps: embeddings are keyed by the registry
  name, so swapping its model silently reuses old vectors; and brief freshness
  ignores the lookups setting, so turning lookups on needs briefs marked stale.
- **Pin each repo separately.** In a multi-repo tree, only the repo a task
  changes moves to its pre-task commit; every other repo stays put. Never pin
  all repos to one date. Never move, sync or rebuild a tree without a go for
  that exact step.
- **Name sources exactly as their repo** (`exigodb`), never with a pin or eval
  prefix. The name is the first segment of every path in briefs and exports.
  Keep pins apart by database, not by source name.
