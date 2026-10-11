---
name: hrono-config
description: Use when the user wants to connect this project to an hrono tree, change where its map is exported, or turn automatic hrono recall on or off.
allowed-tools: [Read, Edit, Write, Bash(git rev-parse --show-toplevel), Bash(hrono profile current*), Bash(hrono tree config list*)]
---

# hrono - configure this project

Settings live in `~/.hrono/agent.json` (`$HRONO_HOME/agent.json` if set),
one entry per project, keyed by its git root (`git rev-parse
--show-toplevel`). Edit the file directly:

```json
{
  "projects": {
    "/path/to/project": { "tree": "bcreg", "recall": true }
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `tree` | none | The tree that maps this project. Nothing runs until it is set. |
| `folder` | `~/.hrono/exports/<tree>` | Where the map is exported and read. |
| `recall` | `true` | Attach recalled passages to every prompt. |
| `limit` | `5` | Passages per prompt. |
| `levels` | `4` | Hops from `root.md` to a leaf in the export. |
| `shortest` | `20` | Prompts shorter than this get no recall. |
| `longest` | `12000` | The most recalled text attached to a prompt. |
| `bin` | `hrono` | The hrono command. |

To connect a project: check the CLI is signed in (`hrono profile current`),
list the trees (`hrono tree config list`), ask which one maps this project,
set `tree`, then export with hrono-export. Recall changes apply from the next
prompt; the session note from the next session.
