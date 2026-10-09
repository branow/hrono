# E048 followups (minor, from qa round 1)
- The new test helper re-imports json locally as `_json` though the module already imports `json` at the top; tests/server/test_ui_browser.py:496 — drop the local import and use `json`.
