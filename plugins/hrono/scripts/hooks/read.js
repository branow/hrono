// @ts-check
"use strict";
// PostToolUse on Read: keep track of the pages of the map the model reads, and
// when it reads a project file, name the brief that describes it - once per
// brief - so the rules around that file are one read away instead of unknown.

const hook = require("../lib/hook");
const map = require("../lib/map");
const settings = require("../lib/settings");

/**
 * @param {settings.Settings | null} config
 * @param {import("../lib/hook").Input} event
 * @returns {string | null}
 */
function pointer(config, event) {
  if (!config || !event.file) return null;
  const log = map.journal(event.session);
  if (map.inside(config.folder, event.file) !== null) {
    log.add("read", [map.real(event.file)]);
    return null;
  }
  const file = map.inside(config.root, event.file);
  if (file === null) return null;
  const fresh = (map.sources(config.folder).get(file) ?? []).filter(
    (brief) => !log.hasRead(map.real(brief)) && !log.hasPointed(brief),
  );
  if (fresh.length === 0) return null;
  log.add("pointed", fresh);
  return (
    `hrono: ${file} is described in ${fresh.join(" and ")}. ` +
    "The brief states the rules the project applies around this file and the " +
    "other places the same data or work reaches; read it before changing the " +
    "file or copying it as a pattern."
  );
}

if (require.main === module) {
  hook.run("PostToolUse", (event) => pointer(settings.load(event.cwd), event));
}

module.exports = { pointer };
