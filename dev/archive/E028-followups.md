# E028 followups (qa, minor)

- `isolation.json` redaction is untested: dropping `redact(...)` at .e2e/eval/run.py:165 leaves all 48 eval tests green; add a test that runs `main` with a fake probe whose reply quotes an address and asserts isolation.json has none.
- `render_isolation` (.e2e/eval/run.py:~617) is not redacted, and `main` prints it to stderr when the probe fails (run.py:168), which now happens on every run; it only stays clean today because the reply preview is cut short. Run it through `redact()` too.
- The isolated haiku reply also named the operator's company ("Techery"), from the injected context and not shaped like an email, so neither the probe nor `redact()` catches it. Consider adding it to the probe or documenting it in .e2e/eval/README.md.
- Both tickets landed in one commit (4e5c07b) instead of one per ticket.
- The pre-existing README line over 80 columns is still there: .e2e/eval/README.md:36 (`--only q01,q05` ...). Reflow it.
