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
        "brief.md files for the names in the question and read the leaf " +
        "briefs that match. Then read the brief.md of the folder above each: " +
        "its Flows name every part a piece of work passes through and what " +
        "each does when a step fails. Follow the work to its end - every part " +
        "that receives it, and what retries or repairs a failed step - and " +
        "read those parts' briefs too, and those under a leaf's Connected " +
        "topics. Then open the source files to confirm " +
        "the claims you " +
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
