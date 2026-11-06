// @ts-check
"use strict";
// PreToolUse on Edit and Write: an edit waits until the map's overview and the
// brief of the file being edited have been read. Advice to read the map first
// is skipped (measured on webERP: one read of root.md in 135 calls); a refusal
// that names the pages to read is not. Only pages that exist are asked for,
// so a model that reads them always gets through.

const fs = require("node:fs");
const path = require("node:path");

const hook = require("../lib/hook");
const map = require("../lib/map");
const settings = require("../lib/settings");

// More than this in one refusal is a reading list, not a next step.
const MOST_ASKED = 3;

/**
 * @param {settings.Settings | null} config
 * @param {import("../lib/hook").Input} event
 * @returns {string | null}
 */
function refusal(config, event) {
  if (!config || !config.gate || !event.file) return null;
  const root = path.join(config.folder, "root.md");
  if (!fs.existsSync(root)) return null;
  const file = map.inside(config.root, event.file);
  if (file === null) return null;
  const log = map.journal(event.session);
  const unread = [root, ...(map.sources(config.folder).get(file) ?? [])]
    .filter((page) => fs.existsSync(page) && !log.hasRead(map.real(page)))
    .slice(0, MOST_ASKED);
  if (unread.length === 0) return null;
  const pages = unread.map((page) => `- ${page}`).join("\n");
  return (
    `hrono: before changing ${file}, read these pages of the project's map ` +
    `(Read each one in full, then make the edit again):\n${pages}\n` +
    "root.md names every area: read the brief of each area the work touches " +
    "too. A leaf brief states the rules the project applies around its files " +
    "and the other places the same data or work reaches - lists, checks, " +
    "reports, permissions, install and upgrade - which a code search does " +
    "not find."
  );
}

if (require.main === module) {
  hook.gate((event) => refusal(settings.load(event.cwd), event));
}

module.exports = { refusal };
