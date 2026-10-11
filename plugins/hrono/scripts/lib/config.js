"use strict";
// The plugin's settings, per repository. One JSON file beside hrono's own
// profile (~/.hrono/agent.json, or $HRONO_HOME) maps a repository's root to
// the hrono tree that describes it, the folder its export is kept in, and
// whether automatic recall is on. Keyed by the git root rather than the
// working directory, so a session started in a subfolder finds the same
// settings.

const { spawnSync } = require("node:child_process");
const { existsSync, mkdirSync, readFileSync, writeFileSync } = require("node:fs");
const { homedir } = require("node:os");
const { dirname, join, resolve } = require("node:path");

const DEFAULTS = Object.freeze({
  recall: true, // attach recalled passages to every prompt
  limit: 5, // passages per prompt
  levels: 4, // hops from root.md to a leaf in the export
  min_chars: 20, // shorter prompts ("yes", "continue") are not recalled for
  max_chars: 12000, // the most recalled text attached to one prompt
  bin: "hrono", // the hrono command
});

const KEYS = ["tree", "export_dir", ...Object.keys(DEFAULTS)];

// ``dataDir`` overrides the location (tests); the hooks and the skills' scripts
// pass none, so they always read the same file.
function file(dataDir) {
  if (dataDir) return join(dataDir, "agent.json");
  return join(process.env.HRONO_HOME || join(homedir(), ".hrono"), "agent.json");
}

function read(dataDir) {
  const path = file(dataDir);
  if (!existsSync(path)) return { projects: {} };
  try {
    const data = JSON.parse(readFileSync(path, "utf8"));
    return { projects: {}, ...data };
  } catch {
    return { projects: {} };
  }
}

function write(dataDir, data) {
  const path = file(dataDir);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(data, null, 2) + "\n");
}

function root(cwd) {
  const found = spawnSync("git", ["rev-parse", "--show-toplevel"], { cwd, encoding: "utf8" });
  return found.status === 0 ? found.stdout.trim() : resolve(cwd);
}

// This repository's settings with the defaults filled in, or null when it has
// no tree configured: an unconfigured repository gets no hrono at all.
function project(dataDir, cwd) {
  const key = root(cwd);
  const stored = read(dataDir).projects[key];
  if (!stored || !stored.tree) return null;
  return {
    ...DEFAULTS,
    export_dir: join(homedir(), ".hrono", "exports", stored.tree),
    ...stored,
    root: key,
  };
}

// Set keys for this repository. Values arrive as strings from the command
// line and are typed by the default they replace.
function set(dataDir, cwd, pairs) {
  const data = read(dataDir);
  const key = root(cwd);
  const current = { ...(data.projects[key] || {}) };
  for (const [name, raw] of Object.entries(pairs)) {
    if (!KEYS.includes(name)) throw new Error(`unknown setting: ${name} (one of ${KEYS.join(", ")})`);
    current[name] = typed(name, raw);
  }
  data.projects[key] = current;
  write(dataDir, data);
  return project(dataDir, cwd);
}

function typed(name, raw) {
  const fallback = DEFAULTS[name];
  if (typeof fallback === "boolean") {
    if (["on", "true", "yes", "1"].includes(String(raw).toLowerCase())) return true;
    if (["off", "false", "no", "0"].includes(String(raw).toLowerCase())) return false;
    throw new Error(`${name} must be on or off`);
  }
  if (typeof fallback === "number") {
    const number = Number(raw);
    if (!Number.isInteger(number) || number < 0) throw new Error(`${name} must be a whole number`);
    return number;
  }
  if (name === "export_dir") return resolve(String(raw).replace(/^~(?=$|\/)/, homedir()));
  return String(raw);
}

module.exports = { DEFAULTS, KEYS, file, project, read, root, set, write };
