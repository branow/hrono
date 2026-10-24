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
 * The passages best first, each named by where it is, while they fit.
 * @param {settings.Settings} config
 * @param {import("../lib/hrono").Hit[]} hits
 * @param {Map<number, string>} pages
 */
function render(config, hits, pages) {
  const head =
    `hrono recall from tree "${config.tree}": the passages most likely to ` +
    "answer this prompt, one per topic, from its sources and from the " +
    "map's briefs. A brief names its page in the map; read the page for " +
    "the whole part.";
  const longest = Math.min(config.longest, INLINE);
  let text = head;
  for (const hit of hits) {
    const block = `\n\n### ${title(hit, pages)}\n\n${hit.body}`;
    if (text.length + block.length > longest) break;
    text += block;
  }
  return text === head ? null : text;
}

/**
 * A passage is named by what a reader can open: its file, or its brief's
 * page in the export (its topic, when the page is not written yet). A source
 * passage also names the page of the topic holding it, when there is one.
 * @param {import("../lib/hrono").Hit} hit
 * @param {Map<number, string>} pages
 */
function title(hit, pages) {
  const page = hit.topic === undefined || hit.topic === null ? undefined : pages.get(hit.topic);
  if (hit.kind === "summary") {
    return page ? `brief of topic ${hit.topic}: ${page}` : `brief of topic ${hit.topic}`;
  }
  const file = hit.path ? (hit.source ? `${hit.path} (${hit.source})` : hit.path) : (hit.header ?? "passage");
  return page ? `${file}, in page ${page}` : file;
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
