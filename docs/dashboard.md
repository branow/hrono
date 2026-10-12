# The dashboard

`hrono serve` serves a web dashboard at `/ui`, from the same process and the
same API as the CLI. This page walks through it page by page.

## Signing in and roles

Sign in with the same token the CLI uses. It is held in an HttpOnly,
SameSite=Strict cookie and resolved by the same role check every API route
uses. A reader sees read-only views; controls a role cannot use are absent as
well as refused.

The dashboard is server-rendered Jinja with no build step and no JavaScript to
vendor. The map, runs, health checks, activity log and config tables are plain
HTML, and every view is a URL you can paste to someone else.

## The menu

The bar has seven sections: Home, Map, Ask, Runs, Health, Export and Settings.
A section with more than one page shows them in a strip under the bar:

| Section | Pages |
|---|---|
| Map | Map, Search, Outline |
| Ask | Recall, Agent demo |
| Runs | Runs, Changes, Usage |
| Settings | Settings, Access (admin only) |

The Guide is the `?` beside your name. The sections and their pages are one
table in `server/ui/__init__.py` (`SECTIONS`), which draws the bar, the strip
and the current-page mark.

## Keyboard access

Everything is reachable from the keyboard. The first Tab stops on a "Skip to
content" link; on the map, a second one skips to the outline, a plain list of
the topics. `/` focuses Search from anywhere that is not a text field. The
tree switcher opens with Enter and folds with Escape. On the map, Tab walks
the topics in drawing order, a ringed disc shows where you are, and Enter
opens the topic and moves focus into its panel.

## Home

Home answers four questions:

- **Is the tree up to date?** Each git source says when it was last read, at
  which commit, and whether its remote has moved on since (asked with
  `git ls-remote`, at most once a minute).
- **Is anything running?** Live, from the same event stream as Runs.
- **What did the last run do?**
- **Does anything need a person?**

Every empty state offers its next step as a button, and every action returns
to the page it came from saying what it did.

## Topics

A topic's page opens with a breadcrumb from the root, then who wrote its brief,
when, and with how many tokens; hashes are behind Details.

- **Previous versions.** A replaced brief, by a run or by hand, is kept (the
  last 5 per topic), each saying who wrote it and what replaced it, with a line
  diff against the current one. Saving a brief unchanged keeps nothing.
- **Sections.** Each shows where it starts (heading, lines, size), worst fit
  first, filterable by path and paged. A section from a repository on
  github.com, gitlab.com or bitbucket.org links to its file at the synced
  commit, on its lines; any other source shows the path alone.
- **Edit and Structure** (admins). Edit changes the name, brief or note;
  Structure reparents, merges, dissolves or splits. Each says what it will
  change before it runs. Moving a section is on the section.
- **Undo.** Edit offers Undo for the topic's latest name, brief or note. It
  says what will change, asks for confirmation and restores the old value. An
  undone brief rewrite goes back to the model and prompt that wrote it, when
  hrono kept them. Structural changes are not undone.
- **Edits.** Every manual edit stays listed, for readers too: what it was, who
  made it, when, and an "undone" tag on those put back.

## Find, Outline and Files

Find is for when you know a word or a file rather than where it sits on the
map. The search box in the top bar looks for every word you type in topic
names, briefs, file paths and file text, grouped by kind. It matches words and
their prefixes and is not semantic; a question in your own words belongs to
Ask.

Outline shows the whole tree as a collapsible list, with each topic's size and
whether recall can answer from it, and stays readable at hundreds of topics.

Files takes a path, or the start of one, to the sections cut from it and the
topic each was filed under. A section waiting to be filed says it is parked; a
path outside the tree's sources says it is not ingested.

## Ask

Ask takes a question in your own words and shows the passages recall would
hand an agent, each with its source, score and topic. When nothing clears the
confidence floor it says so and names topics to explore instead.

The last six questions are kept in this browser only (a cookie, for a day),
each with a compact snapshot of what it returned. Ask one again after a fix and
every passage is marked new, changed, moved from a rank, or the same, and the
ones that dropped out are listed.

## Demo

Demo shows an agent answering from the tree, step by step, as the plugin
would run it in a real session: the recall the hook attached, the prompt the
model received, every map page and source file it opened, lit on the map
beside it, and its answer. Follow-up questions continue the conversation.

It runs on a text model already set up in Settings, picked by its connection
(claude-code, anthropic, openai or openai-compatible), and reads the tree's
kept export, so the tree must be exported first. Asking needs the writer role,
and each call is recorded in Usage. The agent's two tools, `open_topic` and
`open_source`, stand in for the file tools a real agent uses on the export
folder and its own checkout; the page says so.

## Health

Health lists each problem with its fix beside it. An admin can place a waiting
section into its nearest topic or a chosen one, move a section that was placed
without a score (both placements are held by hand, so a sync leaves them in
place), rewrite one stale brief, and hand back any hand edit. Each item says
whether automation will fix it or a person must. A reader sees the same lists
with no controls.

## Runs and Usage

Runs shows every job live: status, progress, sub-steps and spend, split by
stage. A failed run says what stopped it and what to do next, and can be
retried with one click.

A run that changed the tree says what it changed: how many of the tree's
topics it touched, which ones (new, rewritten, regrouped or retired, lit in
the tree), and the sections added and removed. An admin can revert it, which
puts the tree back exactly as it was before the run; syncing again replays
the same change, so a sync can be shown as often as needed. Only the newest
run that changed anything can be reverted, and only while nothing runs.

Usage, open to every role, adds spend up by day, model, run and person. For a
writer or admin it also shows the questions agents asked through recall: the
last 10,000 per tree are kept, with a count per day over the last 30 days, the
share recall was not confident about, and the latest questions, each unsure one
linking to Ask. Questions asked on the Ask page are not counted. A
subscription's figure is marked as an estimate and never added to metered
spend.

## Export

The Export page previews the export's shape (levels, pages per level, widest
page, file count) for a chosen hop limit and downloads it as one archive. Its
Connect an agent block has ready-to-paste commands for the CLI and `curl`
calls to recall and the export, filled with this server and tree. The token
in them is the placeholder `YOUR_TOKEN`; mint a real one on the Access page.

## Set up

Set up is the path for a new install, reached from Home while the tree is
empty and from Settings to add a git source. Four steps, each a real form over
the registry:

1. **A connection**, tested against its provider before it is saved, so a
   wrong key is refused in the provider's own words and nothing is stored.
2. **The models**: an embedding model and one text model per writing role,
   each asked one small question before it is stored.
3. **A source**, fetched, then previewed: the files the filter keeps, the
   largest, and what it leaves out and why. The preview uses the same filter
   ingest uses and makes no model call.
4. **An estimate** of model calls, tokens, time and cost, with its basis
   stated, ending in the build.

A step is done when the registry says so, so leaving halfway and coming back
resumes where you stopped. Nothing is built until the last step.

## Settings

Settings shows one collection at a time (trees, sources, connections, models,
prompts) as a table, with each form field labelled and explained. It says at
the top whether the registry is complete enough to build, and a delete or a
reset shows what it would leave stale before you confirm it.

A brief prompt's form can preview the edit on one topic: "Preview on topic"
runs the unsaved prompt over that topic's inputs with the model a real brief
uses, and shows the result beside the current brief. Nothing is saved, and the
run is counted on Usage like any other.

Values set by the server's environment (version, database path,
`HRONO_LLM_CONCURRENCY`) are shown read-only.

## Access

Access is the admin-only page for who may sign in: list people with their
roles, add one (the new token is shown once and stored only as a hash), change
a role, reissue a token or delete a person. The last admin can be neither
deleted nor demoted, here or through the API.

The master key can be rotated from the same page, which says how many secrets
it re-encrypted. The running server switches to the new key at once; update
the key file before the next restart.
