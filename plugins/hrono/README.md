# hrono for Claude Code

Gives Claude Code the hrono map of the repository it is working in.

- **Automatic recall.** A `UserPromptSubmit` hook asks hrono for the passages
  that answer each prompt and attaches them to it, marked "hrono recall".
  Short prompts and slash commands are skipped; a slow or unreachable server
  never blocks a prompt.
- **The map in every session.** A `SessionStart` hook tells Claude this
  repository is mapped, where the export is and how to walk it.
- **Skills.** `hrono` walks the exported map from `root.md` down to the source
  files; `hrono-export` writes or refreshes the export; `hrono-config` connects
  a repository to a tree and changes the settings.

## Install

```
/plugin marketplace add branow/hrono
/plugin install hrono@hrono
```

It needs the `hrono` CLI on the PATH, signed in to a server
(`hrono profile add <name> --server <url> --token <token>`), and Node, which
Claude Code already has.

## Connect a repository

In the repository, ask Claude to connect it to hrono, or run the config script
yourself:

```
node <plugin>/scripts/config.js set tree=<tree>
node <plugin>/scripts/export.js
```

Nothing happens in a repository with no tree set.

## Settings

Per repository, in `~/.hrono/agent.json` (`$HRONO_HOME/agent.json`):

| Key | Default | Meaning |
|---|---|---|
| `tree` | none | The tree that maps this repository. |
| `export_dir` | `~/.hrono/exports/<tree>` | Where the map is exported and read from. |
| `recall` | `on` | Attach recalled passages to every prompt. |
| `limit` | `5` | Passages per prompt. |
| `levels` | `4` | Hops from `root.md` to a leaf in the export. |
| `min_chars` | `20` | Prompts shorter than this get no recall. |
| `max_chars` | `12000` | The most recalled text attached to one prompt. |
| `bin` | `hrono` | The hrono command. |

## Tests

```
node --test "scripts/tests/*.test.js"
```
