"use strict";
// The hooks and scripts against a fake `hrono` command, so the tests need no
// server: the fake prints what `hrono recall --json` and `hrono tree export`
// would, and records how it was called.

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const SCRIPTS = join(__dirname, "..");

const LOGIN = { kind: "source", header: "git:///m/repo/src/auth.py@abc sp:/login", path: "src/auth.py", source: "repo", body: "def login(): ..." };
const BRIEF = { kind: "summary", header: "node://7", topic: 7, body: "Auth handles sign-in." };

function world(hits = [LOGIN, BRIEF]) {
  const dir = mkdtempSync(join(tmpdir(), "hrono-plugin-"));
  const repo = join(dir, "repo");
  mkdirSync(repo);
  spawnSync("git", ["init", "-q"], { cwd: repo });
  const calls = join(dir, "calls.log");
  const bin = join(dir, "hrono");
  writeFileSync(
    bin,
    `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const args = process.argv.slice(2);
fs.appendFileSync(${JSON.stringify(calls)}, JSON.stringify(args) + "\\n");
if (args[0] === "recall") process.stdout.write(JSON.stringify({ hits: ${JSON.stringify(hits)} }));
if (args[0] === "tree") {
  const out = args[args.indexOf("--out") + 1];
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "root.md"), "# Root\\n");
}
`,
  );
  chmodSync(bin, 0o755);
  const env = { ...process.env, HRONO_HOME: join(dir, "home") };
  const run = (script, args = [], input = "") =>
    spawnSync("node", [join(SCRIPTS, script), ...args], { cwd: repo, env, input, encoding: "utf8" });
  const calledWith = () =>
    existsSync(calls) ? readFileSync(calls, "utf8").trim().split("\n").map(JSON.parse) : [];
  return { dir, repo, bin, run, calledWith };
}

function configured(w, extra = []) {
  const set = w.run("config.js", ["set", "tree=demo", `bin=${w.bin}`, `export_dir=${join(w.dir, "map")}`, ...extra]);
  assert.equal(set.status, 0, set.stderr);
}

function prompt(w, text) {
  return w.run("recall.js", [], JSON.stringify({ prompt: text, cwd: w.repo }));
}

test("an unconfigured repository gets no hrono at all", () => {
  const w = world();
  assert.equal(prompt(w, "how does login work in this service?").stdout, "");
  assert.equal(w.run("session-start.js", [], JSON.stringify({ cwd: w.repo })).stdout, "");
  assert.deepEqual(w.calledWith(), []);
});

test("a prompt gets the recalled passages attached", () => {
  const w = world();
  configured(w);
  const answer = JSON.parse(prompt(w, "how does login work in this service?").stdout);
  const out = answer.hookSpecificOutput;
  assert.equal(out.hookEventName, "UserPromptSubmit");
  assert.match(out.additionalContext, /hrono recall from tree "demo"/);
  // a file the model can open, not the internal address; a brief by topic
  assert.match(out.additionalContext, /### src\/auth\.py \(repo\)\n\ndef login\(\): \.\.\./);
  assert.match(out.additionalContext, /### brief of topic 7\n\nAuth handles sign-in\./);
  assert.doesNotMatch(out.additionalContext, /git:\/\//);
  assert.deepEqual(w.calledWith()[0], ["recall", "demo", "how does login work in this service?", "--json", "--limit", "5"]);
});

test("recall switched off, a short prompt or a slash command attach nothing", () => {
  const w = world();
  configured(w, ["recall=off"]);
  assert.equal(prompt(w, "how does login work in this service?").stdout, "");
  configured(w, ["recall=on"]);
  assert.equal(prompt(w, "yes").stdout, "");
  assert.equal(prompt(w, "/hrono-export please refresh the map now").stdout, "");
  assert.deepEqual(w.calledWith(), []);
});

test("no confident match attaches nothing", () => {
  const w = world([]);
  configured(w);
  assert.equal(prompt(w, "what is the weather like on the moon today?").stdout, "");
});

test("a failing hrono never blocks the prompt", () => {
  const w = world();
  configured(w, ["bin=/nonexistent/hrono"]);
  const answer = prompt(w, "how does login work in this service?");
  assert.equal(answer.status, 0);
  assert.equal(answer.stdout, "");
});

test("the attachment stops before the size limit", () => {
  const long = "x".repeat(400);
  const w = world([1, 2, 3, 4].map((n) => ({ header: `f${n}.py`, body: long })));
  configured(w, ["max_chars=1100"]);
  const text = JSON.parse(prompt(w, "how does login work in this service?").stdout).hookSpecificOutput.additionalContext;
  assert.ok(text.length <= 1100);
  assert.match(text, /### f1\.py/);
  assert.doesNotMatch(text, /### f4\.py/);
});

test("the session opens with where the map is and how to read it", () => {
  const w = world();
  configured(w);
  const before = JSON.parse(w.run("session-start.js", [], JSON.stringify({ cwd: w.repo })).stdout);
  assert.match(before.hookSpecificOutput.additionalContext, /No export is in .*map yet/);
  const exported = w.run("export.js");
  assert.equal(exported.status, 0, exported.stderr);
  const after = JSON.parse(w.run("session-start.js", [], JSON.stringify({ cwd: w.repo })).stdout).hookSpecificOutput.additionalContext;
  assert.match(after, /mapped by hrono \(tree "demo"\)/);
  assert.match(after, new RegExp(`start at ${join(w.dir, "map", "root.md")}`));
  assert.match(after, /matched against the map automatically/);
});

test("export swaps in a complete map and drops pages from the old one", () => {
  const w = world();
  configured(w, ["levels=3"]);
  mkdirSync(join(w.dir, "map"));
  writeFileSync(join(w.dir, "map", "retired-topic.md"), "old");
  const made = w.run("export.js");
  assert.equal(made.status, 0, made.stderr);
  assert.ok(existsSync(join(w.dir, "map", "root.md")));
  assert.ok(!existsSync(join(w.dir, "map", "retired-topic.md")));
  assert.deepEqual(w.calledWith()[0], ["tree", "export", "demo", "--out", join(w.dir, "map") + ".new", "--levels", "3"]);
});

test("settings are refused when the key or value is wrong", () => {
  const w = world();
  assert.notEqual(w.run("config.js", ["set", "colour=blue"]).status, 0);
  assert.notEqual(w.run("config.js", ["set", "recall=maybe"]).status, 0);
  assert.notEqual(w.run("config.js", ["set", "limit=-2"]).status, 0);
});
