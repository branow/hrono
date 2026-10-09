# a brief states a fact without naming the file that settles it

What: in E004's walk-only run (Read/Glob), 10 of 12 export failures were right
answers citing `root.md`: the root brief states TAU 0.70, RRF k 60, the
vector/keyword weights, HRONO_LLM_CONCURRENCY, passage size, HRONO_HOME, and
the agent stopped there with no way to name the section that settles it. With
grep the same shape cost 4 more (q04, q07, q13, q19 cited root.md or a brief.md).

Where: the brief recipe (summarize/brief.py, brief_upper.py prompts) and the
export render (export/render.py) — a brief's concrete constants carry no link
to the section page they came from, although the member references are known.

Why it matters: an agent that cannot cite cannot be checked, and a brief that
paraphrases a constant wrong (none did here) would be uncorrectable from the
export alone. Measured, not fixed, in E004.

Evidence: .autodev/board/evidence/E004/walk/report.md, "Failed paths".
