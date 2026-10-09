# eval isolation still leaks the operator's user context

Found by qa on E027. The export eval's isolation probe reports "verified", but
the isolated session's reply quotes a `userEmail` entry (the operator's email)
from its context: the probe only checks for the CLAUDE.md canary and
a word from the operator's own config, so the harness-injected user context passes unseen, and the email
lands in the evidence reports (`evidence/E027/*-report.md`). The probe should
check for it too, and the runner should strip it or the reports redact it.
Look at: `.e2e/eval/run.py`.
