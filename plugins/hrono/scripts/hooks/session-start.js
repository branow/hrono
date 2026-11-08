// @ts-check
"use strict";
// SessionStart: say that this project has an hrono map, where it is and how
// to read it. A skill is loaded only when the model thinks of it; this note
// puts the map in every session's starting context.

const fs = require("node:fs");
const path = require("node:path");
const hook = require("../lib/hook");
const settings = require("../lib/settings");

/**
 * @param {settings.Settings | null} config
 * @returns {string | null}
 */
function note(config) {
  if (!config) return null;
  const root = path.join(config.folder, "root.md");
  const lines = [
    `This project has an hrono map (tree "${config.tree}").`,
  ];
  if (fs.existsSync(root)) {
    const when = fs.statSync(root).mtime.toISOString().slice(0, 10);
    lines.push(
      `It is exported at ${config.folder} (${when}): plain-text briefs of ` +
        "the whole codebase, in far less text than the code. " +
        `1. Start at ${root}, then read in full the area brief and the leaf ` +
        "briefs of every part your work touches and of the existing flows " +
        "it works like; find them through root.md's links, or Grep the map " +
        "folder for a name or subject. " +
        "2. Take how the system works from the briefs. Open source files " +
        "only to change them or to confirm a claim you rely on. " +
        "3. Skip briefs unrelated to the work.",
    );
  } else {
    lines.push(`It is not exported yet; the hrono-export skill writes it.`);
  }
  if (config.recall) {
    lines.push(
      "Relevant passages are attached to prompts automatically as hrono recall.",
    );
  }
  return lines.join(" ");
}

if (require.main === module) {
  hook.run("SessionStart", ({ cwd }) => note(settings.load(cwd)));
}

module.exports = { note };
