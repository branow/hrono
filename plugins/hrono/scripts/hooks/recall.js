// @ts-check
"use strict";
// UserPromptSubmit: attach what the hrono tree knows about the prompt, so the
// model starts with it instead of having to remember to look.

const fs = require("node:fs");
const path = require("node:path");

const hook = require("../lib/hook");
const hrono = require("../lib/hrono");
const settings = require("../lib/settings");

// Claude Code shows a hook's added context inline only up to 10,000
// characters; past that it saves the text to a file and shows a 2 KB preview,
// which agents rarely open (measured: 1 of 15 runs). So no setting can
// attach more than this.
const INLINE = 10000;

// A prompt that hands the work over in a file ("implement task/brd.md") says
// what the work is in that file, not in its own words, so recall reads the
// files it names. Only text files inside the project, and only so much: the
// embedding reads the start of a query, and the file goes first.
const NAMED = /[\w./-]+\.(?:md|txt|rst)\b/g;
const LONGEST_NAMED = 20000;
const LONGEST_QUERY = 6000;

/**
 * The recalled passages for ``prompt`` as one block of text, or null when
 * there is nothing to attach.
 * @param {settings.Settings | null} config
 * @param {string} prompt
 * @param {string} cwd
 * @returns {string | null}
 */
function attachment(config, prompt, cwd) {
  const question = prompt.trim();
  if (!config || !config.recall) return null;
  if (question.length < config.shortest || question.startsWith("/")) return null;
  const query = [...named(question, cwd), question].join("\n\n").slice(0, LONGEST_QUERY);
  const recalled = hrono.recall(config.bin, config.tree, query, config.limit);
  if (!recalled.ok || recalled.hits.length === 0) return null;
  return render(config, recalled.hits, pageIndex(config.folder));
}

/**
 * The text of each file ``prompt`` names that is a small text file inside
 * ``cwd``, once each.
 * @param {string} prompt
 * @param {string} cwd
 * @returns {string[]}
 */
function named(prompt, cwd) {
  const root = path.resolve(cwd);
  const seen = new Set();
  /** @type {string[]} */
  const texts = [];
  for (const [name] of prompt.matchAll(NAMED)) {
    const file = path.resolve(root, name);
    if (seen.has(file) || !file.startsWith(root + path.sep)) continue;
    seen.add(file);
    try {
      if (fs.statSync(file).size > LONGEST_NAMED) continue;
      texts.push(fs.readFileSync(file, "utf8").trim());
    } catch {
      continue;
    }
  }
  return texts;
}

/**
 * The passages, best first, each headed by where it comes from: the brief it
 * is a slice of, or the file it quotes and the brief that describes that file.
 * One heading per passage, so the reference is stated once.
 * @param {settings.Settings} config
 * @param {import("../lib/hrono").Hit[]} hits
 * @param {Map<number, string>} pages
 */
function render(config, hits, pages) {
  const head =
    `hrono recall from tree "${config.tree}": the passages of the map that ` +
    "best match this prompt, best first. Each is a few lines of a brief or a " +
    "source file; open the brief named with it for the whole part.";
  const longest = Math.min(config.longest, INLINE);
  /** @type {string[]} */
  const blocks = [];
  let size = head.length;
  for (const hit of hits) {
    const block = `\n\n### Passage ${blocks.length + 1}, from ${origin(hit, pages)}\n\n${hit.body}`;
    if (size + block.length > longest) break;
    size += block.length;
    blocks.push(block);
  }
  if (blocks.length === 0) return null;
  return head + blocks.join("");
}

/**
 * Where a passage comes from: the brief's page, or the file and the page of
 * the brief that describes it, when the export has that page.
 * @param {import("../lib/hrono").Hit} hit
 * @param {Map<number, string>} pages
 */
function origin(hit, pages) {
  const page = hit.topic === undefined || hit.topic === null ? undefined : pages.get(hit.topic);
  if (hit.kind === "summary") return page ? `the brief ${page}` : "a brief";
  const name = `the file ${file(hit)}`;
  return page ? `${name}, described in the brief ${page}` : name;
}

/** @param {import("../lib/hrono").Hit} hit */
function file(hit) {
  if (!hit.path) return hit.header ?? "passage";
  return hit.source ? `${hit.path} (${hit.source})` : hit.path;
}

/**
 * Each topic's page in the export, by topic id: a folder is named
 * ``<slug>-<id>`` and holds the topic's brief.md.
 * @param {string} folder
 * @returns {Map<number, string>}
 */
function pageIndex(folder) {
  /** @type {Map<number, string>} */
  const pages = new Map();
  /** @param {string} dir */
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const child = path.join(dir, entry.name);
      const id = /-(\d+)$/.exec(entry.name);
      const brief = path.join(child, "brief.md");
      if (id && fs.existsSync(brief)) pages.set(Number(id[1]), brief);
      walk(child);
    }
  };
  walk(folder);
  return pages;
}

if (require.main === module) {
  hook.run("UserPromptSubmit", ({ cwd, prompt }) =>
    attachment(settings.load(cwd), prompt, cwd),
  );
}

module.exports = { attachment };
