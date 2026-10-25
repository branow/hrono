---
name: hrono
description: Use whenever the session says this project has an hrono map and the question is about what the project's sources hold - an area of a codebase, a system's documentation, how parts fit, where something is. Walks the exported map from the overview down to the source files.
allowed-tools: [Read, Glob, Grep]
---

# hrono - read the map

The map is already exported; the session's opening note gives its folder.
It is a tree of briefs over whatever the tree was built from: repositories,
documentation, wikis. A leaf brief states what its sources do exactly: the
checks that guard each entry point with their conditions, every branch and
the state it sets, what happens on each error, what it sends and receives,
and which other parts it connects to. One brief replaces many file reads.

Read the map from the top down, and read it before any code: a search
over the briefs returns dozens of pages in no useful order, while the
overview names each area in one line.

1. Read the pages "hrono recall" lists on the prompt, when it is attached
   (see below). Then `root.md`: pick every area whose line touches the
   question, and read each one's `brief.md` in full. Its `Flows` name every part a piece
   of work passes through, step by step, what each does when a step fails,
   and the parts elsewhere that repair a step or take the same work.
2. Write down the path: every part the work passes through, from what
   starts it to its last effect (the record applied, the email sent), and
   every part named as a repair or a second path, wherever it sits. A
   part the work is handed to - the one that applies it, the one that sends
   a notice or email about it - is on the path even when the question names
   only the first part.
3. Read the leaf brief of every part on that list - the last parts as much
   as the first: the area brief gives each part a line or two and its
   failure handling as one rule, while the leaf gives the exact conditions,
   what it skips and how each step fails. The area's `## Children`
   links them; grep the briefs for a part's name only when it is not
   there. Each leaf's `Part of` line links its area, and its
   `## Connected topics` the parts it exchanges work or records with:
   follow them to the parts your list is missing.
4. Only then open code, to confirm the claims you will make - the files are
   under each leaf's `## Sources` - not to explore. Where the code and a
   brief disagree, the code wins.
5. Before you answer, go down the list: for every part, have you read its
   brief, and can you say what it does when the work arrives, when it
   fails partway, and when the same work arrives twice? A part you have not
   read is one you would guess about, and guesses are where answers go
   wrong: read it. What the area brief says about a part does not count as
   reading it. Having an answer for the first parts is not a reason to
   stop.
6. In the answer, give every part on the path its own behaviour. Where two
   parts do the same job - an old and a new consumer, two paths for one
   piece of work - say how each one behaves; they rarely match, and "it
   does the same" loses what the question is about.
7. Before you finish, go over the briefs you read - from what you already
   have, without opening them again - and carry into the answer every
   drop, skip and conclusion they state about the parts on the path -
   which work a check silently drops, a sender and receiver that do not
   match, what a second delivery does, a failure nothing repairs - even
   where the question did not ask for it by name. A fact you read and
   left out scores as a fact you never found.

How to spend your turns:
- When "hrono recall" is attached to the prompt, its numbered pages are the
  leaves most likely to hold the answer, best first. Read them before
  `root.md`: the first five at least, and every other one whose passage
  touches the question. Then the overview and the areas, for the parts
  they leave out. A passage is a slice of its page; having read the
  passage is not having read the page.
- Read each brief once. What you read stays in front of you; reading it
  again only spends a turn.
- A brief over about 20 KB: grep it for the question's terms and read
  those parts instead of reading it whole.
- Keep turns for the answer: after about 20 tool calls, stop exploring and
  write it. An answer with what you found beats no answer.

If no export exists, use hrono-export.
