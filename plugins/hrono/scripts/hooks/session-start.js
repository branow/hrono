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
      `It is exported at ${config.folder} (${when}). A leaf brief.md states ` +
        "what its sources do exactly - the checks that guard each entry " +
        "point, every branch and the state it sets, what happens on errors, " +
        "what it sends and receives and from which other parts - so one " +
        "brief replaces many file reads. For a question about how something " +
        "works or how parts fit, before reading code: grep the export's " +
        "brief.md files for the names in the question, read the leaf briefs " +
        "that match, and follow each brief's connections to the briefs of " +
        "the parts on the other side, including what retries or repairs a " +
        "failed step. Then open the source files to confirm the claims you " +
        `make. The hrono skill has the details; for an overview, start at ${root}.`,
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
