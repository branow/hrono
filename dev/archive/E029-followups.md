# E029 followups (qa, minor)

- The new test fakes the probe by monkeypatching `run._probe`; `main` has no probe seam, so DI is not possible without one. Give `main` an injectable probe (as `check_isolation` already has) and pass it in the test — tests/eval/test_export_eval.py:679, .e2e/eval/run.py:163.
- README says "a report and `isolation.json`" are redacted; the stderr isolation report on a failed probe is now redacted too — name it — .e2e/eval/README.md:98.
