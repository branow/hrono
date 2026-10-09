# stale "running server is blind" tests in tests/crypto/test_rotate.py

Found by qa gating E021 (finding 2). After E021 the running server switches to
the new key on rotation, so the two tests whose name/docstring say the server
is now blind describe old behavior (they still pass on the response message).
Rename or delete them so they say what is true.

Blocked for agents: the file holds a GitHub-token-shaped fixture string, so the
secret-scanning hook refuses any read/edit. Needs the user's override tag
once; while there, make the fixture not token-shaped so agents can read the
file afterwards.
