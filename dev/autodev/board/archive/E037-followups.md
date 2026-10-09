# E037 followups (qa, round 1, head bb8daf4)

- README paragraph is wrapped unevenly after the edit ("...when hrono kept / them, and handing the topic / back clears"), README.md:118-120; re-flow the paragraph to 80 columns.
- Three tickets landed in one commit (bb8daf4) instead of one Conventional Commit per ticket; keep to one commit per ticket on later epics.
- The migration's "keep rows" has no test: nothing pins that 0042 copies existing edit_log rows and seeds sqlite_sequence, tests/db/test_migrations.py; add a test that applies migrations up to 0041, inserts an edit_log row, applies 0042 and asserts the row survives and the next id is above it.
