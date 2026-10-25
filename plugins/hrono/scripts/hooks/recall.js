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

/**
 * The recalled passages for ``prompt`` as one block of text, or null when
 * there is nothing to attach.
 * @param {settings.Settings | null} config
 * @param {string} prompt
 * @returns {string | null}
 */
function attachment(config, prompt) {
  const question = prompt.trim();
  if (!config || !config.recall) return null;
  if (question.length < config.shortest || question.startsWith("/")) return null;
  const recalled = hrono.recall(config.bin, config.tree, question, config.limit);
  if (!recalled.ok || recalled.hits.length === 0) return null;
  return render(config, recalled.hits, pageIndex(config.folder));
}

/**
 * A read list of the pages the passages come from, best first, then the
 * passages themselves, numbered to match, while they fit. The list comes
 * first because it is what the model acts on: a passage is a slice, and the
 * page it names states the whole part (measured without the list: the page
 * of the best hit opened in 11 of 30 runs, the rest almost never).
 * @param {settings.Settings} config
 * @param {import("../lib/hrono").Hit[]} hits
 * @param {Map<number, string>} pages
 */
function render(config, hits, pages) {
  const head =
    `hrono recall from tree "${config.tree}": the passages most likely to ` +
    "answer this prompt, one per topic, best first. Each is a slice of a " +
    "page of the map; the page states the whole part. Read the pages " +
    "listed here before anything else in the map, best first, and the " +
    "overview only for the parts they leave out.";
  const heading = "\n\nPages, best first:";
  const longest = Math.min(config.longest, INLINE);
  /** @type {string[]} */
  const list = [];
  /** @type {string[]} */
  const blocks = [];
  let size = head.length + heading.length;
  for (const hit of hits) {
    const n = blocks.length + 1;
    const page = pageOf(hit, pages);
    const line = page ? `\n${n}. ${page}  (${role(hit)})` : "";
    const block = `\n\n### ${n}. ${name(hit)}\n\n${hit.body}`;
    if (size + line.length + block.length > longest) break;
    size += line.length + block.length;
    if (line) list.push(line);
    blocks.push(block);
  }
  if (blocks.length === 0) return null;
  const pagesText = list.length ? heading + list.join("") : "";
  return head + pagesText + blocks.join("");
}

/**
 * The page a passage belongs to: its brief's page in the export, or the
 * page of the topic holding its file; undefined when the export has none.
 * @param {import("../lib/hrono").Hit} hit
 * @param {Map<number, string>} pages
 */
function pageOf(hit, pages) {
  if (hit.topic === undefined || hit.topic === null) return undefined;
  return pages.get(hit.topic);
}

/**
 * What a page is to its passage, for the read list: the brief itself, or
 * the page holding the passage's file.
 * @param {import("../lib/hrono").Hit} hit
 */
function role(hit) {
  return hit.kind === "summary" ? `brief of topic ${hit.topic}` : `holds ${file(hit)}`;
}

/**
 * A passage's own name: its file, or its brief's topic.
 * @param {import("../lib/hrono").Hit} hit
 */
function name(hit) {
  return hit.kind === "summary" ? `brief of topic ${hit.topic}` : file(hit);
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
    attachment(settings.load(cwd), prompt),
  );
}

module.exports = { attachment };
