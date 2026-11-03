# acceptance 2: an upper brief's Name field starts with "# "

- Did: opened topics 17, 18, 19 on the flask copy, Manage > Name.
- Got: the field is prefilled "# Flask repository and docs" ("# ... parent brief" on 17, 18);
  the page's h1 shows the name without "#". Pressing Rename unchanged would store the "#".
- Expected: the same name as the h1.
- From: `src/hrono/server/ui/nodes.py:258` `_first_line(row["brief"])` keeps the markdown
  heading mark; older than this run (18 was not touched). Evidence:
  `dev/evidence/acceptance-2/2026-11-03/ev/gap-name-hash.txt`.
