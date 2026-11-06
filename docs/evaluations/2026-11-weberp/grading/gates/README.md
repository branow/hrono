# Gate and try audits (t7, t8)

Each audit was made by a reading agent (general-purpose subagent, Opus 5.5,
no file changes) given the workspace, the BRD and the checklist; the key
claims were then checked by hand (the README says which). Not blind: the
agent knew which arm it audited. The texts below are the agents' reports
as returned.

- t7-code-gate.md: t7 code-only gate try (17 met / 3 partly / 1 missed)
- t8-code-gate.md: t8 code-only gate try (13 / 7 / 2)
- t8-hrono-1.md: t8 hrono try 1 after plugin 71909d0 (14 / 6 / 2)
- t8-hrono-2.md: t8 hrono try 2 with the brief gate 8874d26 (15 / 5 / 2)

The void t8 hrono try (map never read, runs/void/) was not audited.
