---
name: hrono-export
description: Use when the user asks to export or refresh the hrono map of this project, or the map is missing.
allowed-tools: [Read, Bash(hrono tree export*)]
---

# hrono - export the map

Read this project's entry in `~/.hrono/agent.json` (see hrono-config) for its
`tree`, `folder` (default `~/.hrono/exports/<tree>`) and `levels` (default 4),
then:

```bash
hrono tree export <tree> --out <folder> --levels <levels> --replace
```

`--replace` swaps the new export in only when it is complete and drops pages
of topics that no longer exist. If the command cannot reach the server, show
the error; the CLI needs a signed-in profile (`hrono profile current`).
