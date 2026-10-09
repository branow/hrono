# 26 identical prompt-echo briefs on the #197 db

Found by E003 (dev, T1 Log): the failed maintain on the local demo database clustered 26
level-0 briefs with IDENTICAL text, one degenerate brief that echoes the
prompt. E003 made the clusterer survive it; nothing stops the brief itself.
Suggest: a shape gate for briefs like the condensation one (retry once, never
store an echo), and a way to list stored briefs that fail it.
Look at: src/hrono/summarize/ (brief generation); the local demo database for the input.
