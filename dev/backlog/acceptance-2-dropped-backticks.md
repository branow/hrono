# acceptance 2: "Checked and dropped" shows raw backticks

- Did: opened reviewed topic 17 on the flask copy, unfolded "Checked and dropped (4)".
- Got: "The `.env` over `.flaskenv` priority ... `load_dotenv` isn't defined", backticks raw.
- Expected: identifiers set as code, like the finding statements just above (fixed in E066).
- From: `src/hrono/server/templates/node.html`, the `ul.dropped` items print the text
  without the identifier filter the statements use (`src/hrono/server/ui/__init__.py`).
  Evidence: `dev/evidence/acceptance-2/2026-11-03/ev/o4-topic17-text.txt`.
