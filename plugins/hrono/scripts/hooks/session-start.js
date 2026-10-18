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
        "works or how parts fit, read the map before any code, from the top " +
        `down: start at ${root}, read the brief.md of every area whose line ` +
        "touches the question - its Flows name every part a piece of work " +
        "passes through, what each does when a step fails and what repairs " +
        "it - then the leaf brief of every part on that path, to its last " +
        "part: the area brief only summarises them. " +
        "Only then open the source files, to confirm the claims you " +
        "make; a part whose brief you have not read is one you would guess " +
        "about. The hrono skill has the details.",
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
