---
name: hrono-export
description: Use when the user asks to export, refresh or update the hrono map of this repository, or when the hrono map is missing or out of date. Writes the repository's hrono tree into its export folder.
allowed-tools: [Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/export.js*), Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/config.js show*)]
---

# hrono - export the map

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/export.js
```

Writes this repository's tree into its export folder with
`hrono tree export`, at the configured number of levels. The new export
replaces the old one only when it is complete, so a failure leaves the
previous map in place.

It needs a tree set for this repository and the hrono CLI signed in to a
server (`hrono profile`). If the command says no tree is set, use the
hrono-config skill. If it fails to reach the server, say so and show the
error; do not try another way.

To see which tree, folder and levels it uses:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/config.js show
```
