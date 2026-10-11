"use strict";
// UserPromptSubmit hook: recall from the repository's hrono tree for the prompt
// and attach what comes back, so the model starts with the relevant code
// already in front of it instead of being asked to remember to look.
//
// It never blocks a prompt. Not configured, recall switched off, a prompt too
// short to mean anything, a server that is down or slow: the prompt goes
// through with nothing attached and the hook exits 0.

const { spawnSync } = require("node:child_process");
const { parse } = require("./lib/args");
const config = require("./lib/config");

const TIMEOUT_MS = 15000;

function attachment(settings, prompt) {
  if (!settings || !settings.recall) return null;
  const asked = prompt.trim();
  if (asked.length < settings.min_chars || asked.startsWith("/")) return null;

  const found = spawnSync(
    settings.bin,
    ["recall", settings.tree, asked, "--json", "--limit", String(settings.limit)],
    { encoding: "utf8", timeout: TIMEOUT_MS },
  );
  if (found.status !== 0) return null;

  let hits;
  try {
    hits = JSON.parse(found.stdout).hits;
  } catch {
    return null;
  }
  if (!Array.isArray(hits) || hits.length === 0) return null;
  return render(settings, hits);
}

function render(settings, hits) {
  const head =
    `hrono recall from tree "${settings.tree}" for this prompt: the passages ` +
    "most likely to answer it, from the code and from the map's briefs. " +
    "Check them against the repository before relying on them.";
  let text = head;
  for (const hit of hits) {
    const block = `\n\n### ${title(hit)}\n\n${hit.body || ""}`;
    if (text.length + block.length > settings.max_chars) break;
    text += block;
  }
  return text === head ? null : text;
}

// A source hit is named by its file, which the model can open in this
// repository; a brief by its topic. The raw address is the fallback.
function title(hit) {
  if (hit.kind === "summary") return `brief of topic ${hit.topic}`;
  if (hit.path) return hit.source ? `${hit.path} (${hit.source})` : hit.path;
  return hit.header || "passage";
}

function main() {
  const { flags } = parse(process.argv.slice(2));
  let input = {};
  try {
    input = JSON.parse(require("node:fs").readFileSync(0, "utf8") || "{}");
  } catch {
    return;
  }
  const settings = config.project(flags["data-dir"], input.cwd || process.cwd());
  const text = attachment(settings, String(input.prompt || ""));
  if (!text) return;
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "UserPromptSubmit", additionalContext: text },
    }),
  );
}

if (require.main === module) {
  try {
    main();
  } catch {
    // a hook that throws would put an error in front of every prompt
  }
}

module.exports = { attachment, render };
