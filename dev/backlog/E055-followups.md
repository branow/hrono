# E055 followups (minor, from qa)

- A brief in a language written without spaces (Japanese, Chinese) never forms 6-word runs, so a copy is not caught; `src/hrono/summarize/shape.py` `_runs`; fall back to character n-grams when a text has few word runs.
- A copy stored before the rule (bcreg `hrono-v9.db` 467, 468) is not listed on Health or in `unusable-briefs` until rewritten: `refusal` reads only the stored flag; `src/hrono/summarize/briefs.py` `refusal`; check `shape.copies` against child briefs there, or note it in docs/summarization.md (the new prompt rewrites such briefs anyway, unless the prompt was edited).

(po 2026-11-02: the older brief, condense and judge defaults went to E056 ticket 3; the replay.py title match is evidence tooling, rejected.)
