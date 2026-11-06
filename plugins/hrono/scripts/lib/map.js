// @ts-check
"use strict";
// The exported map as the hooks need it: which leaf brief describes a file,
// and which pages of the map this session has read. A brief lists its files
// under "## Sources", one "- `path`" line each, after a "<source> @ <commit>:"
// line; the path is relative to that source, as it is to the project.

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

/**
 * The briefs that describe each file, by the file's path in its source.
 * @param {string} folder
 * @returns {Map<string, string[]>}
 */
function sources(folder) {
  /** @type {Map<string, string[]>} */
  const index = new Map();
  for (const brief of briefs(folder)) {
    let text;
    try {
      text = fs.readFileSync(brief, "utf8");
    } catch {
      continue;
    }
    const start = text.search(/^## Sources$/m);
    if (start < 0) continue;
    const section = text.slice(start).split(/\n(?=## )/)[0];
    for (const [, file] of section.matchAll(/^- `([^`]+)`/gm)) {
      const known = index.get(file) ?? [];
      if (!known.includes(brief)) index.set(file, [...known, brief]);
    }
  }
  return index;
}

/**
 * Every brief.md under ``folder``.
 * @param {string} folder
 * @returns {string[]}
 */
function briefs(folder) {
  /** @type {string[]} */
  const found = [];
  /** @param {string} dir */
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const child = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(child);
      else if (entry.name === "brief.md") found.push(child);
    }
  };
  walk(folder);
  return found;
}

/**
 * What this session has read of the map and been pointed to, kept in a file
 * per session so every hook call sees the same.
 * @param {string} session
 */
function journal(session) {
  const file = path.join(os.tmpdir(), "hrono-plugin", `${session.replace(/\W/g, "_") || "none"}.json`);
  /** @type {{ read: string[], pointed: string[] }} */
  let state = { read: [], pointed: [] };
  try {
    const data = JSON.parse(fs.readFileSync(file, "utf8"));
    if (Array.isArray(data.read) && Array.isArray(data.pointed)) state = data;
  } catch {
    // a new session
  }
  return {
    /** @param {string} page */
    hasRead: (page) => state.read.includes(page),
    /** @param {string} brief */
    hasPointed: (brief) => state.pointed.includes(brief),
    /** @param {"read" | "pointed"} kind @param {string[]} pages */
    add(kind, pages) {
      const fresh = pages.filter((p) => !state[kind].includes(p));
      if (fresh.length === 0) return;
      state[kind].push(...fresh);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, JSON.stringify(state));
    },
  };
}

/**
 * ``file`` relative to ``root``, or null when it is outside it.
 * @param {string} root
 * @param {string} file
 */
function inside(root, file) {
  const relative = path.relative(real(root), real(path.resolve(root, file)));
  return relative && !relative.startsWith("..") && !path.isAbsolute(relative)
    ? relative.split(path.sep).join("/")
    : null;
}

/**
 * A path with its links resolved, as far as it exists (a file about to be
 * written does not yet).
 * @param {string} file
 * @returns {string}
 */
function real(file) {
  try {
    return fs.realpathSync(file);
  } catch {
    const parent = path.dirname(file);
    return parent === file ? file : path.join(real(parent), path.basename(file));
  }
}

module.exports = { sources, journal, inside, real };
