// @ts-check
"use strict";
// Per-repository settings: which hrono tree describes the repository, where
// its export lives, and how automatic recall behaves. One JSON file beside
// hrono's own profile ($HRONO_HOME/agent.json, default ~/.hrono) holds every
// repository's settings, keyed by its git root, so a session started in a
// subfolder finds the same ones. People (or Claude, through the hrono-config
// skill) edit the file directly; it is external input, checked here, once.

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

/**
 * @typedef {object} Settings
 * @property {string} root       the repository's git root
 * @property {string} tree       the hrono tree that describes it
 * @property {string} folder     where the export is written and read
 * @property {boolean} recall    attach recalled passages to every prompt
 * @property {number} limit      passages per prompt
 * @property {number} levels     hops from root.md to a leaf in the export
 * @property {number} shortest   prompts shorter than this get no recall
 * @property {number} longest    the most recalled text attached to a prompt
 *                               (at most 10,000: Claude Code's inline limit)
 * @property {string} bin        the hrono command
 */

/** @type {Omit<Settings, "root" | "tree" | "folder">} */
const DEFAULTS = Object.freeze({
  recall: true,
  limit: 15,
  levels: 4,
  shortest: 20,
  longest: 10000,
  bin: "hrono",
});

const KEYS = Object.freeze(["tree", "folder", ...Object.keys(DEFAULTS)]);

/**
 * hrono's own folder, where the settings and the default exports live.
 * @param {string | undefined} home
 */
function base(home) {
  return home ?? process.env.HRONO_HOME ?? path.join(os.homedir(), ".hrono");
}

/**
 * Every repository's stored settings. A missing or unreadable file is no
 * settings at all, never an error: an unconfigured machine runs no hrono.
 * @param {string | undefined} home
 * @returns {Record<string, Record<string, unknown>>}
 */
function stored(home) {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(base(home), "agent.json"), "utf8"));
    return isRecord(data.projects) ? data.projects : {};
  } catch {
    return {};
  }
}

/** @param {string} cwd */
function rootOf(cwd) {
  const git = spawnSync("git", ["rev-parse", "--show-toplevel"], {
    cwd,
    encoding: "utf8",
  });
  return git.status === 0 ? git.stdout.trim() : path.resolve(cwd);
}

/**
 * This repository's settings, or null when it names no tree.
 * @param {string} cwd
 * @param {string} [home]
 * @returns {Settings | null}
 */
function load(cwd, home) {
  const root = rootOf(cwd);
  const raw = stored(home)[root];
  if (!isRecord(raw) || typeof raw.tree !== "string" || !raw.tree) return null;
  /** @type {Settings} */
  const settings = {
    ...DEFAULTS,
    root,
    tree: raw.tree,
    folder: path.join(base(home), "exports", raw.tree),
  };
  for (const key of KEYS) {
    const value = key in raw ? parse(key, raw[key]) : null;
    // a value of the wrong kind keeps the default rather than turning the
    // plugin off: one typo should not silently cost every other setting
    if (value !== null) Object.assign(settings, { [key]: value });
  }
  return settings;
}

/**
 * A stored value as the setting's own type, or null when it is not one.
 * @param {string} key
 * @param {unknown} value
 * @returns {string | number | boolean | null}
 */
function parse(key, value) {
  const fallback = DEFAULTS[/** @type {keyof typeof DEFAULTS} */ (key)];
  if (typeof fallback === "boolean") return typeof value === "boolean" ? value : null;
  if (typeof fallback === "number") {
    return Number.isInteger(value) && Number(value) >= 0 ? Number(value) : null;
  }
  if (typeof value !== "string" || !value) return null;
  return key === "folder" ? path.resolve(value.replace(/^~(?=$|\/)/, os.homedir())) : value;
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

module.exports = { load };
