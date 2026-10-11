// @ts-check
"use strict";
// UserPromptSubmit: attach what the hrono tree knows about the prompt, so the
// model starts with it instead of having to remember to look.

const hook = require("../lib/hook");
const hrono = require("../lib/hrono");
const settings = require("../lib/settings");

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
 * @param {settings.Settings} config
 * @param {import("../lib/hrono").Hit[]} hits
 */
function render(config, hits) {
  const head =
    `hrono recall from tree "${config.tree}": the passages most likely to ` +
    "answer this prompt, from its sources and from the map's briefs.";
  let text = head;
  for (const hit of hits) {
    const block = `\n\n### ${title(hit)}\n\n${hit.body}`;
    if (text.length + block.length > config.longest) break;
    text += block;
  }
  return text === head ? null : text;
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
