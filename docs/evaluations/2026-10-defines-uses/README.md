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
