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
    `This project has an hrono map (tree "${config.tree}"): briefs of ` +
      "everything its sources hold, from one overview down to the files.",
  ];
  if (fs.existsSync(root)) {
    const when = fs.statSync(root).mtime.toISOString().slice(0, 10);
    lines.push(
      `It is exported at ${config.folder} (${when}). To understand an area, ` +
        `find where something is, or see how parts fit, use the hrono skill ` +
        `and start at ${root}.`,
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
