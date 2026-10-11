"use strict";
// The hrono-config skill's one command: show or change this repository's
// settings.
//
//   node config.js show
//   node config.js set tree=bcreg export_dir=~/maps/bcreg recall=off

const { parse } = require("./lib/args");
const config = require("./lib/config");

function main() {
  const { flags, positionals } = parse(process.argv.slice(2));
  const dataDir = flags["data-dir"];
  const [command, ...rest] = positionals;
  if (command === "set") {
    const pairs = {};
    for (const pair of rest) {
      const eq = pair.indexOf("=");
      if (eq === -1) throw new Error(`expected key=value, got ${pair}`);
      pairs[pair.slice(0, eq)] = pair.slice(eq + 1);
    }
    print(config.set(dataDir, process.cwd(), pairs));
    return;
  }
  if (command === "show" || command === undefined) {
    const settings = config.project(dataDir, process.cwd());
    if (!settings) {
      console.log(
        `No hrono tree is set for ${config.root(process.cwd())}. ` +
          "Set one with: set tree=<name>",
      );
      return;
    }
    print(settings);
    return;
  }
  throw new Error(`unknown command: ${command} (show or set)`);
}

function print(settings) {
  for (const key of ["root", ...config.KEYS]) {
    console.log(`${key}: ${settings[key]}`);
  }
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
