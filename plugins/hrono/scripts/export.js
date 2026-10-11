"use strict";
// The hrono-export skill's one command: write this repository's tree into its
// export folder.
//
//   node export.js
//
// The export is written into a fresh folder beside the old one and swapped in
// only when it is complete, so a failed export leaves the previous map intact
// and a finished one never carries pages a topic no longer has.

const { spawnSync } = require("node:child_process");
const { existsSync, renameSync, rmSync } = require("node:fs");
const { parse } = require("./lib/args");
const config = require("./lib/config");

function exportTree(settings) {
  const fresh = `${settings.export_dir}.new`;
  const old = `${settings.export_dir}.old`;
  rmSync(fresh, { recursive: true, force: true });
  const made = spawnSync(
    settings.bin,
    ["tree", "export", settings.tree, "--out", fresh, "--levels", String(settings.levels)],
    { encoding: "utf8" },
  );
  if (made.status !== 0) {
    rmSync(fresh, { recursive: true, force: true });
    throw new Error((made.stderr || made.stdout || "hrono tree export failed").trim());
  }
  rmSync(old, { recursive: true, force: true });
  if (existsSync(settings.export_dir)) renameSync(settings.export_dir, old);
  renameSync(fresh, settings.export_dir);
  rmSync(old, { recursive: true, force: true });
  return (made.stdout || "").trim();
}

function main() {
  const { flags } = parse(process.argv.slice(2));
  const settings = config.project(flags["data-dir"], process.cwd());
  if (!settings) {
    throw new Error("No hrono tree is set for this repository; use the hrono-config skill first.");
  }
  const said = exportTree(settings);
  console.log(`Exported tree "${settings.tree}" to ${settings.export_dir}.`);
  if (said) console.log(said);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

module.exports = { exportTree };
