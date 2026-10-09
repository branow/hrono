---
id: E023
title: the rotation tests say what is true, and the file is readable
priority: low
depends_on: [E021]
requirements: []
---

## Goal
Two tests in tests/crypto/test_rotate.py say the running server is blind after
a rotation; after E021 it is not. Agents cannot fix them: the file holds a
GitHub-token-shaped fixture, so the secret-scanning hook refuses it.

## Tickets

### 1 rename or delete the stale blind-server tests
Change: make the fixture not token-shaped; rename or delete the tests whose
name/docstring say the server is blind (incl.
test_the_response_says_the_running_server_is_now_blind).
Done when:
- [ ] no test in the file claims the running server is blind
- [ ] an agent can read the file without the secret-scanning hook refusing it
Look at: tests/crypto/test_rotate.py

## Out of scope
- any production change

## Log
- 2026-10-03 po: created from backlog stale-blind-server-tests (qa E021 r1 finding 2). needs-user: one secret-scanning override grant so a dev may open the file and de-tokenize the fixture? (rec: yes, after E021 merges)
- 2026-10-03 po: E021 merged (fbc291f); depends_on met, waits only on the secret-scanning override grant.
- 2026-10-04 main session: user granted the secret-scanning override; fixed in c3ca086 (renamed the fixture, replaced the two blind-server tests with one on the restart message; mutation on the message killed).
