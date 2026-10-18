# Defines/uses links: does a brief that sees its connections state more?

Experiment, 2026-10-14, on the v3 tree (`~/hrono-eval/db/hrono-v3.db`). The
slice is the 21 leaf pages behind three hard questions (fee waiver, payment
notification, two payment listeners; `../2026-10-links/`), all 574 of their
sections. Harness: `harness/exp.py`; everything it wrote is in `data/`
except `names.db`, which `link` rebuilds.

## What was changed

1. **Condense** (Haiku 4.5, thinking off): the v3 condense prompt plus two
   lists, `defines` (names this content creates that others can call, send
   to or refer to) and `uses` (names from elsewhere it calls, sends to,
   receives from or reads, with a direction and one line on what passes).
   570 of 574 valid, $6.01.
2. **Link** (no LLM): every name goes into two SQLite FTS5 tables, `porter
   unicode61 remove_diacritics 2` and `trigram`. Code names are split into
   words first (`create_invoice`, `createInvoice` → `create invoice`); names
   inside calls are pulled out (`config.get('PAYMENT_SVC_URL')`). A use
   links to:
   - a section that defines the same name;
   - a section that receives what it sends (or the reverse);
   - a section that touches the same channel (topic, subject, queue,
     service URL).

   Porter only finds candidates. It makes "filing" into "file", so a match
   must also be the whole name up to a plural, or its qualified tail
   (`create_invoice` = `PaymentService.create_invoice`). Trigram is tried on
   a miss, at 0.9 similarity. A name on more than 3 leaves (6 for a channel),
   or on more than 15 leaves of the whole tree's sources, is not a link.

   Uses no slice section defines were looked up in the whole tree; the 430
   outside sections found were condensed the same way ($5.41), as a full
   build would have them. Result: 2,651 links, 2,615 by porter and 36 by
   trigram, 1,236 of them leaving the slice.
3. **Briefs** (Sonnet, thinking off). Arms:
   - **B0**: the v3 brief prompt and the CHECKS rule (a check comes with its
     condition) over the new notes. $1.68.
   - **B**: B0 plus a CONNECTED ELSEWHERE block: the notes of up to 12 linked
     sections in other leaves, links into another top folder first, and a
     7th point asking for each connection with the condition on each side.
     $2.42.
   - **C**: B plus the 6 level-1 parents rewritten with a LINKS block (up to
     80 lines of leaf-to-leaf links) and a request to tell the flows across
     them. $2.81.

## How it was scored

Each of the questions' 22 verified facts was split into short yes/no claims
(Sonnet): 135 claims, 38 tagged `connection` (they relate two components or
need both) and 97 `local`. A Sonnet judge says, for each claim, whether the
pages of the fact's leaves and their parents state it, quoting the words.
Every arm was judged twice.

The arms compared:
- **A-v3**: the stored briefs.
- **A-v3x**: the earlier rewritten slice from `2026-10-links`.
- **B0, B, C**: the arms built here.
- **notes**: the new condensations of the fact's own cited files. This is
  the ceiling, the detail a brief is written from.
- **notes-v3**: the same ceiling, with the stored condensations.

## Results

Claims stated, judge run 1 / run 2:

| arm | connection (38) | local (97) |
|---|---|---|
| A-v3 (today) | 5 / 6 | 34 / 32 |
| A-v3x (earlier rewrite) | 7 / 5 | 39 / 34 |
| B0 (new notes, CHECKS) | 9 / 8 | 31 / 33 |
| B (+ linked notes) | 10 / 9 | 34 / 34 |
| C (B + parents with links) | 8 / 9 | 34 / 30 |
| notes, new condensations (ceiling) | 10 / 8 | 33 / 35 |
| notes-v3, stored condensations | 9 / 8 | 44 / 42 |

Claims stated in both judge runs: A-v3 36, B 40.

Connection claims B states in both runs and A-v3 in neither:
- the legal API posts to the payment service with the end user's own bearer
  token;
- business-pay creates a staff Review for continuationIn instead of sending
  it to the filer;
- a second delivery for a PAID, not yet applied filing sends the PAID email
  again and publishes to the filer again (two claims);
- the staff review endpoint publishes approvals to the same NATS filer
  subject.

## Reading

- **Linking by name works once a match is checked.** The first pass, with
  plain FTS phrases, matched `FilingNames` to `file_name` (porter) and
  "transaction schema" to `EFTTransactionSchema` (phrase inside a longer
  name). The whole-name check removed both kinds of error. Channel links
  found the real cross-service edges: `NATS_FILER_SUBJECT` ties the
  future-effective job, the staff review endpoint, business-pay and the
  filer.
- **Some links are still missed or noisy.**
  - pay-api → business-pay is missed: the push subscription never names
    the topic in the consumer's code.
  - Sibling services linked through a shared helper name
    (`register_endpoints`) add noise.
  - Trigram added little: 36 links, several of them wrong
    (`get_review` = `GET /reviews`).
- **Linked notes lift connection claims, not local ones.** Connection
  claims went from 5-6 (A-v3) to 9-10 (B). That is 4-5 claims out of 38,
  stable across both judge runs, and the gained claims are exactly the
  cross-service conclusions these questions turn on. Local claims stayed
  level. This is about +10 points, half the +20 set as the bar for "clearly
  better".
- **Links in the parent briefs added nothing** (C ≈ B). The parents
  describe flows, but the claims are details the leaves hold.
- **The notes are the limit.** B already matches the ceiling: the new notes
  of the exact cited files state 8-10 connection and 33-35 local claims,
  about what the B briefs state. A brief cannot state what its notes
  dropped.
- **Asking for the two lists cost the notes detail.** The new condensations
  hold 9-10 fewer local claims than the stored ones (33-35 against 42-44),
  though they are longer (127 words against 79). Some of the length went to
  the lists' subject matter instead of exact conditions and lists. So B was
  built on weaker notes than A, and still came out ahead on connections.

## Next

1. Keep the condensation prompt as it was, and get `defines`/`uses` from a
   separate cheap call (or a separate output field budget), so the notes keep
   their detail. Check with the notes ceiling alone: 22 judge calls, about
   $1.
2. Work on the ceiling itself: even the stored notes of the exact files
   state under half the local claims. The misses are exact lists (which
   filing types skip waiveFees), conditions and failure handling. A condense
   prompt tuned on these claims is the largest lever; briefs come after.
3. Then rebuild B on the better notes and only then run agents. At +10
   points on 38 claims, an agent run (spread 0.05-0.06 between runs) would
   not resolve it today.

Total cost $29: condense $11.42, briefs $4.10, parents $2.81, claims and
judge about $10.6.

## Reproduce

```
cd harness
uv run --with claude-agent-sdk python exp.py condense
uv run python exp.py expand
uv run --with claude-agent-sdk python exp.py condense-expand
uv run python exp.py link
uv run --with claude-agent-sdk python exp.py brief B0
uv run --with claude-agent-sdk python exp.py brief B
uv run --with claude-agent-sdk python exp.py upper
uv run --with claude-agent-sdk python exp.py claims
uv run --with claude-agent-sdk python exp.py judge r1   # and r2
uv run --with claude-agent-sdk python notes_v3.py r1    # and r2
uv run python exp.py report
```

## Round 2 (2026-10-14): a per-claim judge, ledger notes, rated links

**The batched judge undercounts.** It checks all of a fact's claims in one
call, and it answered "no" with an empty quote on claims the notes state
word for word (for example `if waive_fees -> sets fee_amount, priority_fee,
future_effective_fee and service_fees all to 0`). Every number in the first
table is an undercount. `harness/judge2.py` asks about one claim per call,
with thinking on and the quote asked for before the verdict. 675 calls,
$35.51, no errors.

New arms:
- **notes-ledger**: `harness/ledger.py`, a condense prompt that keeps, line
  by line and verbatim, entry checks, branch rules with every list member,
  the order of saves and failing calls, what each error handler does, calls
  out, states and absences. No word target (183 words a section against 79
  for the stored notes). All 574 slice sections, Haiku, $5.19 for the
  remainder after a usage-limit interruption.
- **BL**: B's prompt over the ledger notes, with the linked sources labelled
  [L1]... and the brief call also rating each as used or not relevant
  (structured output). $3.68.

| arm | connection (38) | local (97) |
|---|---|---|
| A-v3 (today's pages) | 12 | 52 |
| B (pages with linked notes) | 17 | 51 |
| BL (B over ledger notes, links rated) | 15 | 50 |
| notes-v3 (stored notes of the cited files) | 12 | 57 |
| notes-ledger (ledger notes of the cited files) | 13 | 62 |
| raw source (batched judge, a lower bound) | 20 | 76 |

Paired, claim by claim:
- **B against A-v3**: connection +5 / −0, local +10 / −11. The local churn,
  about ten claims each way, is what one judge run moves between two arms of
  equal quality. A gain with no loss on connections is the clear signal.
- **BL against B**: connection +1 / −3, local +12 / −13. Building on the
  ledger notes and rating the links gives nothing on the pages.
- **notes-ledger against notes-v3**: local +18 / −13. The ledger prompt keeps
  somewhat more detail.

**The links rated as not relevant.** 77 of 236 linked sources (33%).
- Most reasons are right: "only shares a name" (`QueueException`, a factory
  pattern, a URL key), unrelated tests, model exports.
- Some are wrong. Five "parallel copies" of filer processors in the data
  tool were dropped, though copies that drift are what hard questions ask
  about. On business-pay's page, pay-api's publisher was dropped as "only
  shares gcp_queue name"; it is the producer of the events business-pay
  consumes.
- As a filter for the next level the rating is usable, but it is not
  reliable enough to delete links.

## Reading, round 2

- **Linking helps where it was meant to.** Connection claims rise from 12
  to 17 of 38 (+13 points) with no claim lost, while local claims stay level.
- **The brief is now where facts are lost, not the notes.**
  - Pages state 50-52 local claims; the notes they are written from state
    57-62.
  - Richer notes do not reach the page: BL's notes are the ledger's, but its
    pages state no more.
  - A 300-900-word brief over 30-50 sections cannot carry every list and
    condition, whatever the notes hold.
- **Condensing loses less than round 1 suggested.** It costs about 15 of 76
  local claims (raw 76, ledger notes 62), not the 30 the batched judge
  showed.

## Next

- **Put the notes in the map, under the page.** hrono already stores a
  condensation per section. The export can render them as the level below a
  leaf page (or as one file per leaf next to its brief), so the page routes
  and summarizes, and the notes carry the lists and conditions. An agent
  that greps the export would then reach 62 of 97 local claims instead of
  50, without opening the code. This keeps the tree and incremental update
  as they are: a note changes only when its section does.
- **Move linking into hrono:**
  - `defines`/`uses` as a second cheap call after condense;
  - the FTS5 matcher (porter for candidates, a whole-name check, channel
    sharing, rarity caps);
  - linked notes in the leaf brief prompt;
  - the brief's used / not-relevant marks stored, for display and for
    pruning parents' link blocks.

  Skip links in parent briefs: C added nothing.
- **Then run agents**, on the four questions with Opus and Sonnet, twice:
  A-v3 pages against B pages plus notes in the export.

Cost so far: round 1 $29, round 2 about $49 (ledger condense $6.08 counting
the cited-section pilot, BL $3.68, per-claim judge $35.51 plus a $1.84
pilot, raw ceiling $2.06).

## Round 3 (2026-10-14): agents on the rebuilt sub-tree

The export `export-bcreg-v3y-L3` (`harness/export_v3y.py`) is the v3 export
with one sub-tree rebuilt:
- the 21 slice leaf topics carry the B briefs;
- their 6 upper topics carry the rebuilt upper briefs (arm C);
- each of the 21 leaf topics has `condensations.md`, the ledger condensation
  of each of its sections, linked from its brief.

Arm `hrono-v3y` in `../2026-10-bc-registries-agents/harness/run_arms.py`:
the same setup as `hrono-v3x` (capped recall over the v3 tree), over this
export. Sonnet, the four questions, two runs, $1.72. The code-only runs are
reused from the earlier evaluation, not rerun.

| arm | run a | run b | mean | errors a / b |
|---|---|---|---|---|
| code only (earlier runs) | 0.52 | 0.46 | 0.49 | 3 / 5 |
| code + rebuilt sub-tree | 0.50 | 0.55 | 0.53 | 5 / 4 |

- **No measurable gain.** +0.04 is inside the 0.06 spread between two
  code-only runs.
- **The condensations were never opened.** No run opened `condensations.md`.
  Every run read briefs: 9 to 23 `brief.md` references per run.
- **The richer content did not reach the agents.** It sits one link below a
  brief, and agents stop at the brief, then go to the code.

## Round 4 (2026-10-14): wide leaf briefs

The seeded brief prompt (`src/hrono/registry/collections/prompts.py`, from
`bd95540`) says "the notes stay available below this description, so leave
detail to them". It also drops lists and enum values and aims for 300-600
words. Nothing below a brief reaches an agent, so that detail is lost.

`harness/wide.py` writes the 21 leaf briefs with a prompt that keeps every
decision, list, condition, error path and call out of the condensations,
with no word target. Input: the ledger condensations plus the linked
condensations of other topics. The briefs average 2,406 words, up to 4,524
(about 700 before); $5.01. The export `export-bcreg-v3z-L3` is v3y with
these leaf briefs and no `condensations.md`; arm `hrono-v3z`, Sonnet, the
four questions, two runs.

| arm | run a | run b | mean | errors a / b |
|---|---|---|---|---|
| code only (earlier runs) | 0.52 | 0.46 | 0.49 | 3 / 5 |
| code + sub-tree, B briefs (v3y) | 0.50 | 0.55 | 0.53 | 5 / 4 |
| code + sub-tree, wide briefs (v3z) | 0.48 | 0.46 | 0.47 | 6 / 6 |

**The wide briefs were barely read.** Counted from the tool calls:
- 4 reads of rebuilt leaf briefs over 8 runs, and only on two questions
  (`hard-failure-1`: 635, 797, 833; `hard-authorization-1`: 577).
- Agents grep the export with `files_with_matches`, which shows file names,
  not text, and then read code.
- Recall attaches briefs from the v3 tree on the server, so it showed the
  old briefs, not these.

So this run does not test whether richer briefs help; they did not reach
the agents.

## Round 5 (2026-10-14): recall serves the rebuilt briefs

In rounds 3 and 4 recall came from the v3 tree on the server, and the
plugin's SessionStart message named the v3x export. So agents got the old
briefs from recall and two exports to start from.

`harness/tree_v3z.py` copies the v3 tree to `hrono-v3z.db`:
- the 21 wide leaf briefs and the 6 rebuilt upper briefs are stored;
- `store_brief` re-splits them into brief passages, and their 1,037 new
  contents are embedded with the tree's model;
- no LLM call.

The server on port 8789 served this copy during the runs; the v3 tree was
restored afterwards. A plugin home `~/hrono-eval/home-v3z`, whose
`agent.json` names the v3z export, was used. Arm `hrono-v3zr`, Sonnet, the
four questions, two runs. (A first attempt ran with the server down, so with
no recall; it is set aside in `runs/void/`.)

| arm | run a | run b | mean | errors a / b |
|---|---|---|---|---|
| code only (earlier runs) | 0.52 | 0.46 | 0.49 | 3 / 5 |
| code + rebuilt sub-tree, recall on its briefs | 0.50 | 0.50 | 0.50 | 4 / 3 |

**What the agents got.**
- Recall attached about 10,000 characters per prompt. The rebuilt briefs
  ranked first (694, 577, 645, 833, 620, 834, 796, 797).
- A wide brief runs 15,000-30,000 characters, so under the 10,000-character
  cap an agent saw the head of one or two of them.
- Agents also opened 0-4 rebuilt leaf briefs per run.

**No gain over code only.** With the rebuilt condensations, linked
condensations in the leaf briefs, wide leaf briefs, rebuilt upper briefs,
and recall serving them, Sonnet scores 0.50 against 0.49 on the four
questions.

On these questions the information in the rebuilt briefs does not change
what Sonnet finds in 30 turns with the code.

## Round 6 (2026-10-15): one question at a time, recall that follows links

From here on, one question at a time, two runs, extended only once it
works.

**Recall cannot reach the topics a hard question needs.**
- On `hard-failure-1`, the leaf topics holding the missed facts rank low
  among 432 by brief passages: the filer (606) 24th, the emailer (579) 19th,
  the repair job (523) 73rd.
- The top topics (796 entity-pay, 577 legal-api, 694 business-pay) are
  linked to them by name: a shared queue subject, a publish call.

`harness/linked_recall.py` builds the block a link-following recall would
attach, within the 10,000-character cap:
- the 3 best topics by brief passages, 2 passages each;
- then linked topics, one hop or two from them, 1 passage each. Topics tied
  to a seed by a channel link (a shared subject, a send matched to a
  receive) come first, then the rest by fit to the question;
- every passage clipped to 700 characters.

The block goes into the prompt where the plugin's hook would put it; the
plugin is off.

**The 400-word answer cap limits every arm.** Both code-only and hrono
answers to `hard-failure-1` filled 400 words with the pay-api half of the
question. They never reached the emailer, the filer or the repair job. The
runs below allow 900 words, for both arms.

| question | arm | runs | coverage |
|---|---|---|---|
| hard-failure-1 | code only, 400 words (earlier) | 2 | 0.36, 0.43 |
| hard-failure-1 | hrono, linked recall, 400 words | 2 | 0.36, 0.43 |
| hard-failure-1 | code only, 900 words | 2 | 0.29, 0.43 |
| hard-failure-1 | hrono, linked recall (by fit), 900 words | 2 | 0.43, 0.57 |
| hard-failure-1 | hrono, linked recall (channel first), 900 words | 2 | 0.43, 0.43 |
| hard-legacy-0 | code only, 900 words | 2 | 0.62, 0.62 |
| hard-legacy-0 | hrono, linked recall (channel first), 900 words | 2 | 0.62, 0.69 |

- **`hard-failure-1`:** hrono 0.47 over four runs against 0.36 for code
  only. The gain is facts 3 and 5 (the legacy listener's duplicate rule; the
  future-effective job as the only repair), which came from the linked
  topics. Fact 6 (the filer commits before its side effects) is missed even
  with the filer in the block: the answers read "processing dies partway"
  as the pay consumer, not the filer.
- **`hard-legacy-0`:** level. The seed topics were a UI test suite and
  auth-web locale files, because the question's plain words ("streaming
  bus", "push-subscription") match no brief well. Neither listener reached
  the block.
- Lifting the cap raised code only on `hard-legacy-0` from 0.44 to 0.62.

**Offline seed check** (`harness/seeds.py`, embeddings only, no agent).
Over the four questions, how many of the 45 leaf topics that hold an
answer's cited files land in the block:

| seeds from | answer topics in the block | in a plain top 9 |
|---|---|---|
| brief passages (as above) | 13 / 45 | 11 / 45 |
| brief passages, test topics skipped | 14 / 45 | 12 / 45 |
| brief and source passages | 16 / 45 | 10 / 45 |
| brief and source passages, test topics skipped | 16 / 45 | 11 / 45 |

Links add a few answer topics over a plain top 9. Still, at most 16 of 45
reach the block: a hard question's answer spans more topics than nine
clipped entries hold.

Spent this round: 14 agent runs, about $3.50.

## Round 7 (2026-10-15): flow topics and a question-time briefing

**Flow topics** (`harness/flows.py`). The leaf topics that have links are
grouped by the link graph: Louvain, channel links weighted up, common names
down. The 4 groups are real flows across areas:
- the pay-api internals;
- the filing-payment flow (legal-api, business-pay, the future-effective
  job, pay-api's endpoints);
- the filings UI;
- the NATS queue workers (entity-pay, the filer, the emailer, the shared
  queue library).

Each got a flow brief written from its members' briefs and the links between
them: 1,400-2,500 words, $2.16. The flow briefs state hand-offs no topic
brief did (the old listener's input shape, the filer committing before its
side effects).

**Choosing a flow for a question fails.**
- Cosine scores of the four flows sit within 0.83-0.89, and the longest wins
  every time.
- Word overlap picks wrong too.
- A hard question spans two or three flows anyway (`hard-failure-1` needs
  the pay-api jobs, business-pay and the repair job, and the queue workers).

**Listed flow briefs are not read.** With the 4 flow briefs in the export
and listed in the recall block with their paths, and the block saying to
open them, no run opened one.

**A question-time briefing** (`linked_recall.py compose`). One Sonnet call
reads the 4 flow briefs and the leaf briefs linked recall picks, and writes
a briefing for the question (verbatim facts, files to verify, what to
check). It goes inline, clipped to 10,000 characters. About $0.60 a
question.

| question | agent | code only, 900 words | hrono briefing, 900 words |
|---|---|---|---|
| hard-legacy-0 | Sonnet | 0.62, 0.62 | 0.69, 0.75 |
| hard-failure-1 | Sonnet | 0.29, 0.43 | 0.36, 0.43 |
| hard-legacy-0 | Haiku | 0, 0 (no answer in 30 turns) | 0 (no answer), 0.44 |
| hard-failure-1 | Haiku | 0, 0 (no answer in 30 turns) | 0.36, 0 (no answer) |

- **Sonnet gains +0.10 on `hard-legacy-0` and +0.04 on `hard-failure-1`.**
- **The briefing held fact 6, and the answers still left it out** (the filer
  commits before its side effects; post-commit failures are swallowed).
- **The tree itself carries a wrong statement.** The future-effective job
  "re-offers only future-effective filings": the job's endpoint returns
  every PAID or APPROVED filing that is due. The briefing passed it on, and
  no run got fact 5.
- **Haiku answered in 2 of 4 runs with the briefing, 0 of 4 without it.** It
  hits 30 turns otherwise.

## What blocks a large, consistent gain

1. **Delivery.** Agents use what recall puts inline (at most 10,000
   characters) and almost never open what is listed: briefs, flow briefs or
   condensations, whatever the instruction says.
2. **Selection.**
   - A hard question needs about 11 leaf topics over two or three flows.
   - Similarity picks the wrong starting topics for plainly worded questions
     (a UI test suite, locale files) and cannot tell flows apart.
   - Links help a little: 16 of 45 answer topics reach the block, against
     10-12 for a plain top 9.
3. **Correctness.** A wrong statement in a brief (the future-effective job)
   travels into everything built on it, and the agent trusts it.
4. **Use.** A fact inline is not a fact in the answer: the agent answers
   from what it read in the code and keeps its own reading of the question.

Spent this round about $6.50: flow briefs $2.16, briefings $1.16, 8 Sonnet
and 8 Haiku agent runs.

## Round 8 (2026-10-15): trace each claim, briefs that look things up

Two questions only (hard-legacy-0, hard-failure-1: 104 claims), Sonnet
agents at 900 words, against the code-only runs `code-w9a/b`.

**Trace: where each claim is lost** (`harness/trace.py`; the per-claim judge
of round 2, now also on the cited source files, arm `raw`):

| layer | claims stated (of 104) |
|---|---|
| source of the cited files | 75 |
| stored condensations | 57 |
| stored leaf briefs and their upper briefs | 56 |
| ledger condensations (round 2) | 58 |
| ledger2 condensations (this round) | 60 |
| wide leaf briefs W (round 4) | 65 |
| investigating leaf briefs I (this round) | 76 |

Why claims were lost:
- **Condensation.** The seeded prompt aims at 60-120 words. The ledger
  prompt also dropped the shape of what arrives, the order of an entry's
  checks, polling loops and the path of an HTTP call. `ledger2`
  (`harness/ledger.py`) asks for these: 58 -> 60. What remains is mostly
  phrasing (states named, but not tied to the branch that sets them).
- **Brief.** The seeded brief prompt says the notes "stay available" (they
  do not), leaves out lists and enum values, and keeps at most three hazards.
- **Connections.** The wrong future-effective statement came from here. The
  job's condensation lists the config key `LEGAL_API_URL` among its uses,
  not the endpoint `/internal/filings/future_effective`, so no link to
  legal-api's route was made, and the brief described the endpoint from its
  name. The same happens with queues: business-pay publishes to
  `config["EMAIL_PUBLISH_OPTIONS"]["subject"]`, the emailer subscribes
  through its own key, and name matching cannot connect them.

**Investigating leaf briefs** (`harness/investigate.py`): the brief writer
(Sonnet) gets two tools over the condensations of all 5,545 sections of the
tree, `search` (SQLite FTS5) and `read`. Before writing, it finds the other
side of each message, call and shared record, what an endpoint it calls
really selects, and what repairs a failed step. 16 topics, 3-10 lookups
each, $4.27. The future-effective job's brief now says the endpoint returns
"ids of PAID or APPROVED filings with effective_date <= now". Local claims
59 of 74 (source 59), connection claims 16 of 30 (source 16).

The writer still gives up on some counterparts: the emailer's consumer
("not found in the condensations"), what the filer does with a PAID filing.
It searches only the stored (short) condensations, and topics written in
the same pass cannot see each other's new briefs.

**Agents.** Export `export-bcreg-v3w-L3` is v3z without flow briefs and
`condensations.md`; each leaf brief of the slice ends with
`## Linked topics` (paths to linked topics' briefs, from `links.json`).
`export-bcreg-v3i-L3` is the same with the I briefs. The instruction says
what a brief holds and how to use it (`MAP_V2`, `MAP_V3` in
`harness/agent_v2.py`); no recall block.

| arm | legacy-0 | failure-1 |
|---|---|---|
| code only (`code-w9a/b`) | 0.62, 0.62 | 0.29, 0.43 |
| question-time briefing (round 7) | 0.69, 0.75 | 0.36, 0.43 |
| W briefs + links, `MAP_V2` (`m2`) | 0.69, 0.69 | 0.50, 0.50 |
| I briefs + links, `MAP_V2` (`i2`) | 0.69, 0.69 | 0.36, 0.50 |
| I briefs + links, `MAP_V3` (`i3`) | 0.69, 0.69 | 0.43, 0.50 |
| ceiling: the question's 13 I briefs inline (`o2`) | 0.56, 0.62 | 0.71, 0.71 |

- With the old instruction ("the map points you to the right files") agents
  read 1-3 briefs and went to the code. `MAP_V3` (trace the work end to end
  through Connections first) gets them to read 5-7 briefs, the filer and
  the future-effective job among them.
- failure-1: the I briefs carry enough for 0.71 when the agent has all of
  them; agents that find their own way get 0.43-0.50. The gap is which
  briefs an agent reaches and what it takes from them.
- legacy-0: the ceiling is no higher than code only. The answers are good;
  what they miss are facts the question does not ask for directly (the
  order of business-pay's auth and empty-body checks, the payload wrapper).
  A 900-word answer chooses; this question does not separate the arms.
- Cost per run is the same as code only ($0.17-0.58).

**Also found:** 7 of the 21 W briefs begin with a note the Claude CLI's
environment leaked into the answer ("the claude.ai Gmail ... connectors need
authorization"). Only harness-written briefs; none in the stored tree.
`investigate.clean` strips it.

Spent this round about $55: the per-claim judge $42 (the raw source and the
long W and I briefs are large inputs), briefs $4.27, condensations $0.97,
16 agent runs $6.70. The judge is now the expensive part; next rounds judge
only changed briefs, and score agents first.

## Round 9, step 1 (2026-10-15): does the brief writer say which lookups it used?

A lookup into another branch is a dependency incremental update does not
know about. The plan stores only the lookups that shaped the brief, as
relations an update follows, so first: is the writer's `Used` list reliable?
`harness/lookup.py` gives the new seeded brief prompt read-only tools shaped
like Claude Code's `Grep`, `Glob` and `Read` over virtual files
`source/<repo>/<path>` and `condensed/<repo>/<path>.md` - what exists when a
leaf brief is written in a real build (condense runs over every section
first); no briefs. Own condensations from the new seeded condense prompt.
Three topics, $1.16.

- **future-effective job (523):** 5 lookups, 3 declared, each declared file
  holds its statement. The brief now says the endpoint returns "the ids of
  filings with status PAID or APPROVED and effective_date <= now" (from
  legal-api `models/filing.py`). $0.18.
- **business-pay (694) and entity-pay (797):** the writer looked up little
  (2-5 calls of 15) and marked the filer and emailer "(behaviour not in this
  topic)" without looking: the new brief prompt's rule gave it an easy way
  out. After the instruction said to look first, it still stopped after 4
  calls with weak finds (the emailer's `get_recipients`, not its consumer).
- Declarations: no statement about another part came from an undeclared
  file; entity-pay once declared its own files (now filtered in code) and
  once wrote paths in its own form (now the instruction asks for the tools'
  form). The own files were labelled without their repository, so guessed
  paths missed; now labelled with the full path, and a lookup that finds
  nothing says how paths begin.

So far: what is declared is accurate; what is looked up is too little for
two of three topics.

## Round 9, steps 1-4 (2026-10-15): lookups in hrono, a sub-tree rebuilt by hrono's own code

**Step 1, end.** With the connections it found listed in a `## Lookups`
section and thinking on, the writer made 8-11 lookups on business-pay and
entity-pay (it had made 2-5), found the entity-filer consumer and legal-api's
Filing model, and said which ones it could not find. Declarations stayed
accurate. Step 1 in all: $1.70.

**Steps 2-3, in hrono** (commits `509f683`, `b468a0c`): a tree setting
"Look into other topics" (off by default); tool use in every provider
(`llm/tools.py`); virtual `source/` and `condensed/` files with read-only
`Grep`, `Glob`, `Read` (`summarize/lookup.py`); the `brief_uses` table; and
`propagate` judging a leaf whose used file changed. See docs/summarization.md.

**Step 4: the two questions' sub-tree, rebuilt by hrono's own ops**
(`harness/subtree_v9.py`, a copy of the v3 tree, `hrono-v9.db`): the new
seeded prompts, the setting on, the 380 sections of the 16 leaf topics
re-condensed by the `condense` op (every other section keeps its stored
condensation), the 16 leaf briefs by the `brief` op with lookups (26 stored
relations, `data/brief-uses-v9.json`), the 9 upper briefs above them by the
`brief-upper` op, the export by hrono's renderer (`export-bcreg-v9-L3`). The
agents get what the plugin now says (its session note and the hrono skill,
`MAP=plugin` in `agent_v2.py`), no recall block.

- **Upper briefs with no word target ran away**: the root reached 13,600
  words, a level-2 brief 10,600. The upper prompt got back a 400-900 word
  range (its children's briefs are below it in the map); rewritten, they are
  1,200-2,700 words. Leaf briefs are 750-5,700 words.
- In this run the future-effective job's brief did not find the query behind
  the endpoint; it says "what that endpoint queries and returns is not shown
  in the lookup" instead of guessing.

| arm | legacy-0 | failure-1 |
|---|---|---|
| code only (`code-w9a/b`) | 0.62, 0.62 | 0.29, 0.43 |
| round 8 best (I briefs + links, `MAP_V3`) | 0.69, 0.69 | 0.43, 0.50 |
| **hrono v9: own code, new prompts, lookups, plugin text** | 0.75, 0.62 | 0.64, 0.57 |

failure-1 averages 0.61 against 0.36 for code only, close to the round 8
ceiling (0.71 with every needed brief inline); legacy-0, the question that
does not separate the arms, 0.69 against 0.62. The agents read 4-12 briefs
and cost the same as code only ($0.26-0.48 a run).

Spent in step 4: about $13 at API prices (billed to the subscription through
the `claude-code` provider): condense $1.70, leaf briefs $3.40, upper briefs
$4.00 and their rewrite $1.60, four agent runs and their scoring $2.40. Over
the $5-8 estimate, because of the runaway upper briefs.

## Round 9, what the v9 run showed (2026-10-15, no new calls)

Read from the four agent transcripts, the 16 leaf and 9 upper briefs, the 380
condensations and the 26 stored relations of the v9 run.

**Where each missed fact was.** failure-1 lost the legacy consumer's
duplicate rule (fact 3), the emailer tracker (fact 4) and the filer's partial
failure (fact 6). All three are stated in leaf briefs - entity-pay (797), the
entity-emailer worker and tracker (579: every `message_id` rule,
`is_processable_message` returning False for a None id, the `MSG_RETRY_NUM`
cap), the filer processors (607) - that no agent opened. Both answers treated
"processing dies partway" only at business-pay and never followed the work to
the filer and emailer.

**Why agents did not get there.**
- The area brief over business-pay, filer and emailer (459) has a `Flows`
  section that walks exactly that chain, with what each step leaves behind on
  failure. The export cut every upper page to its opening paragraph
  (`export/render.py` `_routing`), so no agent could see it.
- A service is split into a logic topic and a packaging-and-tests topic with
  near-identical titles ("business-pay queue service"); one legacy-0 run read
  only the packaging one and went to the code.
- business-pay's brief named the filer and emailer subjects but said "what
  the filer does with the message is not in this topic": its lookup stopped
  at entity-filer's `config.py`, which names the subject, not what consumes
  it. The leaf briefs give up on 1-8 connections each and keep 1-3
  relations, several of them helpers (`base_model.py`, an example runner).
  The run used no thinking; the pilot that looked deep did.
- The brief text cited the tools' virtual paths (`condensed/...config.py.md`),
  which do not exist in the export.

**A wrong fact, and where it came from.** Haiku condensed
`return {}, HTTPStatus.NOT_FOUND` as "503 NOT_FOUND" (1 of 85 number-name
pairs in the tree's condensations disagrees, and this is the one). The brief
kept it ("503 (the code names it NOT_FOUND)"), the area flow kept it, and one
answer repeated it; the other run caught it by reading the code. The area
flow also said "no part retries" a lost filer message, where the repair job
lives in another area.

**Not a tree problem.** legacy-0's half scores are mostly facts the question
does not ask (the order of business-pay's checks) or comparisons across two
briefs the agent read (the legacy consumer expects a `paymentToken` wrapper
the pay API no longer sends). Both answers ran past the 900-word cap.

**Fixed** (commits `751c52a`, `f2490c6`):
1. Export: middle pages keep their flows and hazards (not the per-part list
   their children listing repeats); only the root is cut to its opening.
2. Condense prompt: a constant, status or error code is written as the code
   writes it, never as the number it stands for.
3. Lookups instruction: reach the handler that acts on a message, not the
   file that names it; for a shared record, the other owner's rules that
   apply or are bypassed; Used only for files on the other side of a
   connection; never the tools' paths, and any that slip in are rewritten.
4. Brief calls with lookups think (budget 4,000), in every provider.
5. A brief opens with a title saying what its topic holds.
6. Upper flows say no part of their area repairs a step, not that none does.
7. Plugin: read the area brief above each leaf for its flows, and follow the
   work to its end.
8. Each lookup brief stores its tool calls and its own account of every
   connection, so a later run can be audited without paying again.

## Round 10, the sub-tree rebuilt with the round 9 fixes (2026-10-16)

`subtree_v9.py build` then `export` on a fresh copy of the v3 tree (round 9's
db and export kept as `hrono-v9-round9.db`, `export-bcreg-v9-round9`): 380
condensations, 16 leaf and 9 upper briefs, 10 stored relations (26 in v9).

**What the fixes did.**
- No condensation turns a status name into a number any more (0 against 1).
- No brief cites the tools' virtual paths.
- The area brief over business-pay, filer and emailer (459) reaches the
  export with its `Flows` and `Hazards`: the filer's commit-then-side-effects
  failure, the emailer tracker, and "no part retries" are all on the page.

**What they did not do.** Half the leaf briefs (8 of 16: 577, 579, 606, 644,
694, 728, 744, 834) made no lookup at all; their audits name every connection
"not searched". Neither input size (12k-67k chars) nor topic explains which
ones. The other 8 made 1-7 calls. business-pay's legacy worker (797) still
says the filer consumer's "behaviour is not in this topic" and did not search
for it.

**A harness bug.** `MAP=plugin` was never wired in `agent_v2.py`:
`map_plugin()` existed but `run` fell back to the round 8 `MAP_V2` text. The
v9 runs and the first v10 pair (`v10a/b`) never saw the plugin's "read the
area brief, follow the work" note. Fixed; `v10c/d` are the runs with it.

| arm | legacy-0 | failure-1 |
|---|---|---|
| code only (`code-w9a/b`) | 0.62, 0.62 | 0.29, 0.43 |
| hrono v9 (round 8 text) | 0.75, 0.62 | 0.64, 0.57 |
| hrono v10a/b (round 8 text) | 0.69, 0.62 | 0.57, 0.50 |
| **hrono v10c/d (plugin text)** | 0.75, 0.69 | 0.64, 0.57 |

With the round 8 text the agents read 2-4 leaf briefs and never the area
brief. With the plugin text both failure-1 runs read 459, and failure-1
averages 0.61 against 0.36 for code only, as in v9.

**Where the facts are lost now: in the answer, not the tree.** Fact 4 (the
legacy consumer re-sends the email and the filer message on a second delivery
unless the filing is COMPLETED) is in 797's `Hazards` word for word, and both
failure-1 agents read 797; they scored 0 and 0.5 on it. The emailer
tracker's filing-type rule (fact 5) is only in the emailer leaf (579), which
no agent opened; 459's flow names the tracker but not the rule. Fact 2
(when BCOL, PAD, EFT and EJV release the payment event) sits in sbc-pay's
service-layer brief, outside this sub-tree's lookups.

**Fixed** (this commit):
1. A leaf brief written with lookups that made no tool call is asked once
   more, with a note that it named its connections without searching
   (`lookup.UNLOOKED`); the instruction now says the brief comes after the
   lookups, never instead of them.
2. `agent_v2.py` honours `MAP=plugin`.

### Round 10, fact by fact (no new calls)

Every fact either answer missed or half-stated, traced to the step that lost
it (`v10c/d`, plugin text):

| fact | in the tree? | where it was lost | fix |
|---|---|---|---|
| failure-1 #2 (BCOL/PAD/EFT/EJV release at invoice creation) | yes, spread over 833 | 833 is one leaf of 54 sections, a 440-line brief; the agent read lines 30-130 | cold build splits leaves over `MAX_CAP` |
| failure-1 #4, legacy-0 #6 (legacy consumer's duplicate rule) | yes, 797 Hazards word for word | read by both agents; one wrote "does the same job" | skill: give each parallel part its own behaviour |
| failure-1 #5 (emailer tracker skips other filing types) | yes, 579 | 459's flow kept "unseen or FAILED" but dropped the silent skip; nobody opened 579 | upper prompt: a flow says where a step drops work without an error |
| failure-1 #6 (future-effective job re-drives lost PAID filings) | yes, 523 (its lookups found the query) | 523 is in another area; 459 never names it; 694 made no lookup; 523's relations were dropped | export `## Connected topics`; `Used` repository paths kept; lookup retry |
| failure-1 #7 (an uncaught error in consume_nr skips the later steps) | partly: 606 did not look into business_profile / name_request | 459 wrote "failures in these steps are logged and swallowed" for all steps | upper prompt: failure per step, never one rule; lookup retry |
| legacy-0 #7, hazard (`verify_gcp_jwt` "may be inverted") | wrong in the tree | Haiku condensed `if msg := verify_gcp_jwt(...)` -> 403 as "returns truthy (fails -> 403)"; 694 flagged the contradiction; 459 made it a hazard | condense and brief prompts: a check as the code tests it |
| legacy-0 #5 (business-pay's own Filing model bypasses legal-api's listener) | no | 694 made no lookup, so the shared-record rule never ran | lookup retry |

**Faults found in hrono itself:**
1. `lookup.split` dropped every `Used` line written as a repository path
   (which round 9's instruction asked for in the brief text): 16 of 26
   relations lost, 523's three among them. Now a bare path that names a
   tree file is kept.
2. The export never rendered `brief_uses`. A leaf page now has `## Connected
   topics`: the topics on the other side of a looked-up relation, in both
   directions, with what was taken. On v10 it links 796, 797, 775, 606, 607,
   555, 619, 834, 833 and 635.
3. The cold `cluster` op never enforced `MAX_CAP`: 62 of 432 bcreg leaves held
   31-65 sections (30% of the corpus). It now splits them with repair's
   split; 52 of the 62 split (833 into three), 10 have no two density cores.
4. A brief that made no lookup, or whose own `Lookups` account says a
   connection was not searched, is asked once more with a fresh budget and
   the list of what it skipped. On v10 that is all 16 briefs, so the
   instruction now says the first replies are lookups and an unsearched
   connection sends the brief back.
5. Prompts: checks as the code tests them; upper flows give failure handling
   per step, name silent drops, and say what no part of the area repairs.
6. The plugin points at `Connected topics` and asks for each parallel part's
   own behaviour.

## Round 11, the round 10 fixes rebuilt and run (2026-10-16)

`subtree_v9.py build` (now splitting leaves over `MAX_CAP` first: 5
oversized leaves became 14, 25 leaf briefs), then `uppers` and `export`.
v10's db and export kept as `hrono-v10.db`, `export-bcreg-v10`; the leaves
before the upper changes as `hrono-v11-leaves.db`.

**What the fixes did, checked in the briefs before any agent ran.**
- Every leaf brief looked things up: 6-18 calls each (v10: 8 of 16 made
  none). 121 relations stored (v10: 10). What leaves still call "not
  searched" is budget, not refusal (a model file, a helper's body).
- `verify_gcp_jwt` is right everywhere (694: a non-empty string -> 403).
- 694 states business-pay's own filing model bypasses legal-api's listeners.
- 606 links the future-effective job (523) under `Connected topics`.
- 833 split three ways; `complete_post_invoice` -> `_release_payment` per
  method is in 870.

**Faults found in the rebuilt tree, fixed before the agent runs.**
1. 459 still wrote "no part retries" a lost filer message: the
   future-effective job that does sits in another area, and an upper brief
   reads only its children. Upper input now ends with `Outside this area`:
   each topic elsewhere a leaf here exchanged a statement with, its opening
   line, what passed and its hazards (`briefs.outside`).
2. The first rebuild put those parts in a section of their own; the prompt
   now asks for them inside the step they repair or duplicate.
3. Given business-pay's opening line alone, 454 wrote that neither consumer
   has a duplicate guard: outside topics now carry their hazards.
4. A changed outside section never made an upper brief stale (a rebuild
   wrote nothing): it is now part of the upper's member signature.

After them 459's flow says: "Nothing in this area retries it, but the
future-effective-filings job (elsewhere) republishes ids of PAID or APPROVED
filings whose effective date has arrived", and names entity-pay as a second
path.

| arm | legacy-0 | failure-1 |
|---|---|---|
| code only (`code-w9a/b`) | 0.62, 0.62 | 0.29, 0.43 |
| hrono v10c/d (plugin text) | 0.75, 0.69 | 0.64, 0.57 |
| hrono v11a/b (plugin text) | 0.50, 0.63 | 0.50, 0.57 |

**Why it did not show: the agents never read the area brief.** Briefs opened
per run: v10c/d failure-1 opened 459 (found by chance in a grep); no v11 run
did. v11a failure-1 opened no brief at all and worked from the code with 19
Bash calls; the others opened 694 and 797 and went to the code. A leaf page
had no link up to its area, so an agent that lands on a leaf by search never
learns the area brief exists. Every fact v11 lost against v10 (failure-1 #5
the tracker's filing types, #7 the per-step failure after commit; legacy-0
#5 the listener bypass) is either in 459 or in a leaf no run opened, and one
run's swing on a fact (0.5 -> 0) is the whole difference between rounds: two
runs per arm cannot separate a 0.1 change from noise.

**Fixed after the runs** (no new agent calls):
1. Every page below the root now opens with `Part of [area](path)`: the
   area brief that says how work moves and what repairs a failed step.
2. The upper prompt asks a silent drop to be said as what the dropped work
   is (which types, which states), never only as the field its check reads.
   459 still writes "without a usable id" for the tracker's filing-type
   rule; the rule stays in the emailer leaf (579).

## Round 12, agents told to read the map top down (2026-10-18)

Same export as round 11 plus the `Part of` links (leaves not rebuilt: the
lookup-order change in `a885f85` is not in these briefs). Skill and session
note now: start at `root.md`, read the area briefs, list every part on the
path, read each part's brief, then confirm in code. Four runs per question.
The judge now says why each fact fell short and quotes each wrong
statement; every earlier arm was re-scored with it (old scores in
`~/hrono-deep/runs/judge-v1/`).

| arm | failure-1 | legacy-0 |
|---|---|---|
| code only (w9a/b) | 0.29, 0.43 (avg 0.36) | 0.56, 0.62 (0.59) |
| hrono v10c/d | 0.64, 0.57 (0.61) | 0.75, 0.69 (0.72) |
| hrono v11a/b | 0.50, 0.57 (0.54) | 0.56, 0.56 (0.56) |
| **hrono v12a-d** | 0.71, 0.71, 0.64, 0.50 (0.64) | 0.75, 0.75, 0.75, 0.56 (0.70) |

**What changed in behaviour.** Every v12 run opened `root.md`, then the
filing area (459) and the payments areas, then 5-10 leaves: 8-14 briefs per
failure-1 run against 0-3 in round 11. Cost per failure-1 run rose from
$0.45 to $0.65.

**What is still lost, from the judge's reasons:**
1. legal-api's filing model sets PAID on save when a payment date is set:
   missed in 6 of 8 runs, and 3 runs say the opposite ("entity-pay never sets
   PAID"). The old consumer's leaf (797) never looked that model up; the
   lookup-order fix targets it, but these leaves predate it.
2. The emailer drops messages of filing types outside its list: missed in
   all 4. No run opened the emailer leaf (579) or the filer leaf (606): the
   agents read the payment side leaf by leaf, then took the filer and
   emailer from the area brief alone, which says only "skips messages
   without a usable id" and "post-commit errors go to Sentry".
3. The filer's per-step failure (fact 7) is 0.5 in every run, for the same
   reason: the area brief's one rule, copied.
4. Online banking is listed among `complete_post_invoice` callers (2 runs):
   a wrong merge of two paths from the payments leaf (870).
5. legacy-0's payload-shape mismatch and the listener bypass are read but
   never drawn as consequences.

## Round 13, leaves rebuilt with the lookup fixes (2026-10-18)

`subtree_v9.py leaves` (25 leaf briefs, 9 uppers, condensations kept), after
four one-leaf pilots on the old listener (797) that ended in the save-hook
note (`d007453`): a read or grep that touches a file with save hooks shows
them. 797 now states that committing `payment_completion_date` makes legal-api's
`receive_before_change` set PAID. A re-run of business-pay (694) looked up
nothing on legal-api's model this time and states the listener bypass only
vaguely. Four runs per question.

| arm | failure-1 | legacy-0 |
|---|---|---|
| code only | 0.36 | 0.59 |
| v12 (top-down skill) | 0.64 | 0.70 |
| **v13** | 0.71, 0.86, 0.57, 0.71 (0.71) | 0.69, 0.62, 0.62, 0.75 (0.67) |

Agents read 14-17 briefs per failure-1 run ($0.65-0.99, one hit the 30-turn
cap). The PAID rule now reaches the answers ("the legal-api listener derives
PAID").

**Still lost:**
1. failure-1 fact 7 is partly wrong in the reference: `consume_nr` and
   `publish_mras_email` catch every exception (checked in the code); only
   `update_business_profile` and `update_entity` have no handler. The
   briefs never say those two have none, so every answer generalises "the
   post-commit steps go to Sentry". Next: the brief must say where nothing
   catches an error.
2. The emailer's filing-type list (fact 5) is in the emailer leaf; the one
   run that read it still left it out.
3. legacy-0: the payload-shape mismatch is read but never concluded ("would
   skip every event"); the empty-body 200 before the JWT check is missed;
   business-pay's own model is vaguer than in v12.
4. More wrong statements on the pay side (PAD and EFT release timing):
   failure-1 errors 1-3 per run against 1-2 in v12.

## Round 14, absences stated and conclusions drawn (2026-10-19)

`611d2db`: the condense prompt writes what content lacks (a step nothing
handles, a case no rule covers), for any kind of content; the brief gains a
Conclusions section (what a dropping check drops, whether two sides of a
connection match, which steps an unhandled failure skips, what a change
would and would not reach); upper flows carry those conclusions.
`subtree_v9.py leaves --condense`: 380 condensations rewritten (267 carry an
ABSENT line), 25 leaf briefs, the uppers. Two network failures midway; the
re-runs skipped the fresh briefs. Four runs per question.

| arm | failure-1 | legacy-0 |
|---|---|---|
| code only | 0.36 | 0.59 |
| v13 | 0.71 | 0.67 |
| **v14** | 0.79, 0.64, 0.79, 0.64 (0.72) | 0.81, 0.69, 0.75, 0.69 (0.73) |

legacy-0's shape mismatch went from 0.38 to 1.0 in every run: the old
listener's brief now concludes it would skip every message the pay API
sends. Errors fell (failure-1 1-2 per run, legacy-0 none).

**Still lost, by cause:**
1. The condenser loses or reorders rules in dense code. The emailer
   tracker's `if message_id is None -> not processable` is gone (all rules
   packed on one line), so the brief concludes such messages are "not
   deduplicated" when they are never processed (failure-1 fact 5).
   business-pay's checks come out with the JWT check before the empty-body
   check, the reverse of the code, so no answer says an empty body gets 200
   unauthenticated (legacy-0 fact 7).
2. A conclusion drawn in the narrow direction. The future-effective job's
   brief says "filings still in the future are not returned"; nothing says
   its `effective_date <= now` also picks up a lost immediate filing, so
   three of four answers trust the job's name and write "nothing repairs an
   immediate filing" (failure-1 fact 6, the main wrong statement).
3. Conclusions not drawn: what a second delivery does to the old listener
   (a PAID filing is re-applied, re-emailed, re-filed; fact 4), and that a
   status-rule change in legal-api does not reach business-pay's own model
   (legacy-0 fact 5).
4. failure-1 fact 7 is wrong in the reference: `consume_nr` catches every
   exception and `update_business_profile` reports error statuses to
   Sentry (only an exception from the request escapes). Answers saying so
   are scored as wrong.
