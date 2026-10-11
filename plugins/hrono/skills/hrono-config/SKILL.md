---
name: hrono-config
description: Use when the user wants to connect this repository to an hrono tree, change where its map is exported, or turn automatic hrono recall on or off.
allowed-tools: [Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/config.js*), Bash(hrono profile current*), Bash(hrono tree config list*)]
---

# hrono - configure this repository

Settings are per repository, kept in `~/.hrono/agent.json`.

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/config.js show
node ${CLAUDE_PLUGIN_ROOT}/scripts/config.js set key=value [key=value ...]
```

| Key | Default | Meaning |
|---|---|---|
| `tree` | none | The hrono tree that maps this repository. Nothing happens until it is set. |
| `export_dir` | `~/.hrono/exports/<tree>` | Where the map is exported and read from. |
| `recall` | `on` | Attach recalled passages to every prompt (`on` / `off`). |
| `limit` | `5` | Passages attached per prompt. |
| `levels` | `4` | Hops from `root.md` to a leaf in the export. |
| `min_chars` | `20` | Prompts shorter than this get no recall. |
| `max_chars` | `12000` | The most recalled text attached to one prompt. |
| `bin` | `hrono` | The hrono command. |

## Connecting a repository for the first time

1. Check the CLI is signed in: `hrono profile current`. If not, the user adds
   a profile with the server URL and a token (`hrono profile add`).
2. List the trees: `hrono tree config list`, and ask which one maps this
   repository.
3. `config.js set tree=<name>`, then export the map with the hrono-export
   skill.

Changes apply from the next prompt; the export path in the session's opening
note applies from the next session.
