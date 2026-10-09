# orchestrator — how the loop runs (hrono autodev)

The orchestrator is the main session. It is also the **PO**: it authors and
triages tickets, does the final review, and is the only one who talks to the
user. It writes no production code.

It starts **two long-lived agents, dev and qa, once**, and keeps them for the
whole run. All shared state is the filesystem under `.autodev/board/`; agents
never talk to each other, only through the board.

## Roles and their prompts

- PO  -> `.autodev/loop/prompts/po.md` (the orchestrator itself)
- dev -> `.autodev/loop/prompts/dev.md`
- qa  -> `.autodev/loop/prompts/qa.md`

## Long-lived agents — the point of this design

dev and qa are started once and **never killed or replaced while the run is
alive**. Their context — what they learned about the codebase, what they
already tried, what the other side keeps finding — is the asset. A fresh agent
per ticket pays for that understanding again every time.

- Start each with the Agent tool, telling it to read its prompt file.
- An agent only returns when the board has nothing for it (see below). When new
  work appears for an agent that has returned — a new ticket, a kickback, a
  ruling — **continue the same agent with SendMessage**. Never spawn a second
  dev or a second qa.
- Spawn a replacement only if an agent is truly lost (crashed, or its context
  is exhausted), and say so to the user.

## The pipeline is parallel, not a relay

```
backlog -> todo -> in-progress -> verifying -> po-review -> done
            ^           dev            qa          PO
            |___________ kickback ______|___________|
```

- **dev** takes a batch of tickets, not one. It commits each ticket separately
  and moves each to `verifying/` the moment it is finished, then goes straight
  on to the next. It does not wait for qa.
- **qa** reviews whatever is in `verifying/` while dev keeps building. It gates
  each ticket's commit in an isolated git worktree, so dev's unfinished work in
  the shared tree never colours the result.
- A ticket qa or the PO rejects goes back to `todo/` with findings. dev picks
  kickbacks up **before** any new ticket, as soon as its current ticket is
  committed.
- The **PO** reviews `po-review/` in batches whenever it is awake, and triages
  `backlog/`.

Nobody idles by returning. An agent with nothing to do right now runs
`.autodev/loop/wait-for-board.sh`, which blocks until a ticket moves:

- exit 0 — the board changed; look again
- exit 2 — nothing moved yet; look again, then wait again
- exit 3 — `todo/`, `in-progress/`, `verifying/` and `po-review/` are all
  empty: the board is drained. Only then does an agent report and return.

## What the orchestrator does

1. Make sure the working tree is clean and `todo/` holds ready tickets.
2. Start dev and qa in the background, once.
3. Keep its own background watch (`wait-for-board.sh`) so it wakes when the
   board moves. Each time it wakes:
   - review everything in `po-review/` (close, or kick back with findings);
   - triage new files in `backlog/`;
   - check the invariants below;
   - if an agent has returned and there is work for it, SendMessage it;
   - start the watch again.
4. Answer a stop condition raised by an agent: rule on it as PO when the
   ruling is cheap to reverse, record the ruling in the ticket, and continue
   that agent. Ask the user only for decisions that are unsafe or wasteful to
   guess.

## Invariants (checked each time the orchestrator wakes)

- Every ticket file is in exactly one stage folder.
- A ticket in `verifying/` names its commit in its Review log, and that commit
  exists on `main`.
- Nothing has sat in `in-progress/` without a Review-log line for it.
- `board.md` is the PO's file. dev and qa never edit it — three writers on one
  table is how it went wrong before. The folders are the truth; the PO
  regenerates the table from them.

If an invariant fails, fix the board if the cause is obvious, otherwise stop
that ticket and say what is wrong.

## Stop conditions

The loop does **not** stop while any ticket is outside `done/` or `backlog/`.
It ends only when:

- the board is drained and the PO has nothing left to author or promote; or
- every remaining ticket is blocked on a decision only the user can make — in
  which case everything that does not depend on that decision is finished
  first, and the questions are put to the user together.

## This run

- Goal: carry #201-#219 to `done/`, plus whatever the backlog triage promotes.
- Mode: unsupervised. No pause between handoffs.
- Commits go straight to `main`, one per ticket.
