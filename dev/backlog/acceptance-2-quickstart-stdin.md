# acceptance 2: the README Quickstart's config commands fail as written

- Did: followed README Quickstart, `hrono connections set claude -f - <<'EOF' ... EOF`
  (same for `models set emb`, `models set writer`, `sources set repo`, README:43-56).
- Got: `Invalid value for '-f' / '--file': File '-' does not exist.` Nothing is written.
- Expected: `-f -` reads stdin (the usual convention), or the README shows the form that works.
  Without `-f -` the same heredoc works (`--help`: "omitted, the config is read from stdin").
- From: `src/hrono/registry/commands.py` `set_item`: `--file` is a `Path` with `exists=True`,
  so `-` is checked as a file. Older than this run (7a3d7e0). Either accept `-` as stdin
  or drop `-f -` from README. Evidence: `dev/evidence/acceptance-2/2026-11-03/ev/gap-quickstart-stdin.txt`.
