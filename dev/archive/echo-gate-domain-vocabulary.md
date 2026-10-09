# Echo gate can still flag a real brief whose topic is the prompt's vocabulary

Found by qa on E015 round 2 (0518beb). `echoes()` in
`src/hrono/summarize/shape.py` compares a brief's words with its prompt's
words, less a function-word list. "caution" (the brief prompt asks for a
'Caution:' section) and "group" ("This group ...") are in nearly every real
brief, so a real brief needs only 6 more of the prompt's 22 other words. A
brief about a config/INI parser (section, names, items, lines, state,
identical) or a parent brief written while hrono indexes a tree-shaped
codebase, hrono itself included (node, parent, child, level, briefs, below),
reaches 8 shared words and 30%. Realistic examples land at 6 or 7 today.

A flagged brief is never fresh, so it is rewritten on every maintain at two
calls each, forever. Options: drop words the prompt tells the model to write
("caution"); count only prompt words absent from the node's own material
(children's text is in the database); or cap the rewrites of a flagged brief
the way T2 caps refused condensations.
