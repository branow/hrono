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
const MORE = "\n\nMore pages:";

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
  return render(config, recalled.hits);
}

/**
 * The hits as map pages to read, best first; a hit whose page is not in the
 * export (none written yet) is attached as its passage instead.
 * @param {settings.Settings} config
 * @param {import("../lib/hrono").Hit[]} hits
 */
function render(config, hits) {
  const head =
    `hrono recall from tree "${config.tree}": the map pages most likely to ` +
    "cover this prompt, best first. Each says what its part does, its checks " +
    "and failure handling, and which files hold it.";
  const pages = pageIndex(config.folder);
  const longest = Math.min(config.longest, INLINE);
  // the best pages whole while they fit, then the rest as one line each: a
  // page only pointed at is rarely opened (2026-10-bc-registries-v2/)
  let whole = head;
  let pointers = "";
  for (const hit of hits) {
    const page = hit.topic === undefined ? undefined : pages.get(hit.topic);
    if (!page) {
      const block = `\n\n### ${title(hit)}\n\n${hit.body}`;
      if (whole.length + pointers.length + block.length <= longest) whole += block;
      continue;
    }
    const full = `\n\n### ${page}\n\n${read(page)}`;
    const line = `\n- ${page} : ${summary(page)}`;
    if (!pointers && whole.length + full.length <= longest) whole += full;
    else if (whole.length + MORE.length + pointers.length + line.length <= longest)
      pointers += line;
  }
  const text = pointers ? `${whole}${MORE}${pointers}` : whole;
  return text === head ? null : text;
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

/** @param {string} page */
function read(page) {
  try {
    return fs.readFileSync(page, "utf8").trim();
  } catch {
    return "";
  }
}

/**
 * A page's title and its first sentence.
 * @param {string} page
 */
function summary(page) {
  const lines = read(page).split("\n").map((line) => line.trim());
  const heading = (lines.find((line) => line.startsWith("# ")) ?? "").slice(2);
  const first = lines.find((line) => line && !line.startsWith("#")) ?? "";
  const sentence = (first.match(/^.*?[.!?](\s|$)/) ?? [first])[0].trim();
  return heading ? `${heading}. ${sentence}` : sentence;
}

/**
 * A passage is named by what a reader can open: its file, or its brief's topic.
 * @param {import("../lib/hrono").Hit} hit
 */
function title(hit) {
  if (hit.kind === "summary") return `brief of topic ${hit.topic}`;
  if (hit.path) return hit.source ? `${hit.path} (${hit.source})` : hit.path;
  return hit.header ?? "passage";
}

if (require.main === module) {
  hook.run("UserPromptSubmit", ({ cwd, prompt }) =>
    attachment(settings.load(cwd), prompt),
  );
}

module.exports = { attachment };
