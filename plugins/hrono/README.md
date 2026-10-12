# hrono for Claude Code

Gives Claude Code the hrono map of a project: briefs of everything the
project's sources hold (repositories, documentation, wikis), from one overview
down to the files.

- **Recall, automatically.** A `UserPromptSubmit` hook asks hrono for the
  map pages that match each prompt and attaches them, marked "hrono recall":
  each page's path, title and first sentence, best first (a page not yet
  exported is attached as its passage).
  Short prompts and slash commands are skipped, and a slow or unreachable
  server never blocks a prompt.
- **The map in every session.** A `SessionStart` hook says the project has a
  map, where its export is and how to read it.
- **Skills.** `hrono` walks the export from `root.md` down to the sources;
  `hrono-export` writes it with `hrono tree export --replace`; `hrono-config`
  explains the settings file, which Claude edits directly.

## Install

```
/plugin marketplace add branow/hrono
/plugin install hrono@hrono
```

It needs the `hrono` CLI on the PATH with a signed-in profile, and Node, which
Claude Code already has. Nothing runs in a project until its tree is set in
`~/.hrono/agent.json`; ask Claude to connect the project, or see the
`hrono-config` skill for the format.

## Code

`scripts/hooks/` holds the two hooks; `scripts/lib/` the settings reader, the
hrono CLI call and the hook input/output. Plain JavaScript type-checked with
JSDoc, so nothing needs installing.

```
node --test "scripts/tests/*.test.js"
```
