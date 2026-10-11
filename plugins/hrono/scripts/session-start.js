"use strict";
// SessionStart hook: tell the model, in every session, that this repository has
// an hrono map, where it is and how to read it. A skill alone is loaded only
// when the model thinks of it; this makes the map part of the starting context.

const { existsSync, statSync } = require("node:fs");
const { join } = require("node:path");
const { parse } = require("./lib/args");
const config = require("./lib/config");

function context(settings) {
  if (!settings) return null;
  const root = join(settings.export_dir, "root.md");
  const lines = [
    `This repository is mapped by hrono (tree "${settings.tree}").`,
  ];
  if (existsSync(root)) {
    const when = statSync(root).mtime.toISOString().slice(0, 10);
    lines.push(
      `The map is exported at ${settings.export_dir} (exported ${when}). For ` +
        "any question about how this codebase is organised, what a part of it " +
        "does or where something lives, walk the map with the hrono skill: " +
        `start at ${root}, follow the child that fits, and open the files a ` +
        "leaf lists under Sources in this repository.",
    );
  } else {
    lines.push(
      `No export is in ${settings.export_dir} yet; the hrono-export skill ` +
        "writes one.",
    );
  }
  if (settings.recall) {
    lines.push(
      "Prompts are also matched against the map automatically: relevant " +
        "passages arrive attached to the prompt, marked as hrono recall.",
    );
  }
  return lines.join(" ");
}

function main() {
  const { flags } = parse(process.argv.slice(2));
  let input = {};
  try {
    input = JSON.parse(require("node:fs").readFileSync(0, "utf8") || "{}");
  } catch {
    // no input is fine: fall back to the working directory
  }
  const text = context(config.project(flags["data-dir"], input.cwd || process.cwd()));
  if (!text) return;
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: text },
    }),
  );
}

if (require.main === module) {
  try {
    main();
  } catch {
    // never fail a session start
  }
}

module.exports = { context };
