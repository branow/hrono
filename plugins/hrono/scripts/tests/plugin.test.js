"use strict";
// The hooks against a fake `hrono` command and a settings file written the way
// a person or Claude writes it, so the tests need no server.

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const HOOKS = path.join(__dirname, "..", "hooks");

const LOGIN = {
  kind: "source",
  header: "git:///m/repo/src/auth.py@abc sp:/login",
  path: "src/auth.py",
  source: "repo",
  body: "def login(): ...",
};
const BRIEF = { kind: "summary", header: "node://7", topic: 7, body: "Auth handles sign-in." };

/** A project, a fake hrono that answers recall with ``hits``, and a home. */
function world(hits = [LOGIN, BRIEF]) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "hrono-plugin-"));
  const project = path.join(dir, "project");
  fs.mkdirSync(project);
  spawnSync("git", ["init", "-q"], { cwd: project });
  const root = spawnSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: project,
    encoding: "utf8",
  }).stdout.trim();
  const calls = path.join(dir, "calls.log");
  const bin = path.join(dir, "hrono");
  fs.writeFileSync(
    bin,
    `#!/usr/bin/env node
require("node:fs").appendFileSync(${JSON.stringify(calls)}, JSON.stringify(process.argv.slice(2)) + "\\n");
process.stdout.write(JSON.stringify({ hits: ${JSON.stringify(hits)} }));
`,
  );
  fs.chmodSync(bin, 0o755);
  const home = path.join(dir, "home");
  const env = { ...process.env, HRONO_HOME: home };

  return {
    dir,
    project,
    /** @param {Record<string, unknown> | null} settings */
    configure(settings) {
      fs.mkdirSync(home, { recursive: true });
      const projects = settings ? { [root]: { bin, ...settings } } : {};
      fs.writeFileSync(path.join(home, "agent.json"), JSON.stringify({ projects }));
    },
    /** @param {string} hook @param {object} input */
    run(hook, input) {
      return spawnSync("node", [path.join(HOOKS, hook)], {
        cwd: project,
        env,
        input: JSON.stringify({ cwd: project, ...input }),
        encoding: "utf8",
      });
    },
    calls() {
      return fs.existsSync(calls)
        ? fs.readFileSync(calls, "utf8").trim().split("\n").map((l) => JSON.parse(l))
        : [];
    },
  };
}

const ASK = "how does login work in this service?";

/** The context a hook attached, or null when it attached nothing. */
function attached(answer) {
  assert.equal(answer.status, 0);
  return answer.stdout ? JSON.parse(answer.stdout).hookSpecificOutput.additionalContext : null;
}

test("a project with no tree set gets no hrono at all", () => {
  const w = world();
  w.configure(null);
  assert.equal(attached(w.run("recall.js", { prompt: ASK })), null);
  assert.equal(attached(w.run("session-start.js", {})), null);
  assert.deepEqual(w.calls(), []);
});

test("a prompt gets its recalled passages, named by file and topic", () => {
  const w = world();
  w.configure({ tree: "demo" });
  const text = attached(w.run("recall.js", { prompt: ASK }));
  assert.match(text, /hrono recall from tree "demo"/);
  assert.match(text, /### src\/auth\.py \(repo\)\n\ndef login\(\): \.\.\./);
  assert.match(text, /### brief of topic 7\n\nAuth handles sign-in\./);
  assert.doesNotMatch(text, /git:\/\//);
  assert.deepEqual(w.calls()[0], ["recall", "demo", ASK, "--json", "--limit", "15"]);
});

test("a brief whose page is in the export is named by that page", () => {
  const w = world([{ ...LOGIN, topic: 7 }, BRIEF]);
  const page = path.join(w.dir, "export", "auth-area-3", "sign-in-7", "brief.md");
  fs.mkdirSync(path.dirname(page), { recursive: true });
  fs.writeFileSync(page, "# Sign-in\n\nChecks a password.\n");
  w.configure({ tree: "demo", folder: path.join(w.dir, "export") });
  const text = attached(w.run("recall.js", { prompt: ASK }));
  assert.ok(text.includes(`### brief of topic 7: ${page}\n\nAuth handles sign-in.`));
  assert.ok(text.includes(`### src/auth.py (repo), in page ${page}\n\ndef login(): ...`));
});

test("recall off, a short prompt or a slash command attach nothing", () => {
  const w = world();
  w.configure({ tree: "demo", recall: false });
  assert.equal(attached(w.run("recall.js", { prompt: ASK })), null);
  w.configure({ tree: "demo" });
  assert.equal(attached(w.run("recall.js", { prompt: "yes" })), null);
  assert.equal(attached(w.run("recall.js", { prompt: `/hrono-export ${ASK}` })), null);
  assert.deepEqual(w.calls(), []);
});

test("no confident match attaches nothing", () => {
  const w = world([]);
  w.configure({ tree: "demo" });
  assert.equal(attached(w.run("recall.js", { prompt: ASK })), null);
});

test("a missing hrono never blocks the prompt", () => {
  const w = world();
  w.configure({ tree: "demo", bin: "/nonexistent/hrono" });
  assert.equal(attached(w.run("recall.js", { prompt: ASK })), null);
});

test("the attachment stops before the size limit", () => {
  const body = "x".repeat(400);
  const w = world([1, 2, 3, 4].map((n) => ({ kind: "source", path: `f${n}.py`, body })));
  w.configure({ tree: "demo", longest: 1100 });
  const text = attached(w.run("recall.js", { prompt: ASK }));
  assert.ok(text.length <= 1100);
  assert.match(text, /### f1\.py/);
  assert.doesNotMatch(text, /### f4\.py/);
});

test("no setting attaches more than Claude Code shows inline", () => {
  const body = "x".repeat(3000);
  const w = world([1, 2, 3, 4, 5, 6].map((n) => ({ kind: "source", path: `f${n}.py`, body })));
  w.configure({ tree: "demo", longest: 24000 });
  const text = attached(w.run("recall.js", { prompt: ASK }));
  assert.ok(text.length <= 10000);
  assert.match(text, /### f3\.py/);
  assert.doesNotMatch(text, /### f4\.py/);
});

test("a setting of the wrong kind keeps its default", () => {
  const w = world();
  w.configure({ tree: "demo", limit: "lots", recall: "yes" });
  assert.notEqual(attached(w.run("recall.js", { prompt: ASK })), null);
  assert.deepEqual(w.calls()[0].slice(-2), ["--limit", "15"]);
});

test("the session opens with where the map is and how to read it", () => {
  const w = world();
  const folder = path.join(w.dir, "map");
  w.configure({ tree: "demo", folder });
  assert.match(attached(w.run("session-start.js", {})), /not exported yet/);

  fs.mkdirSync(folder);
  fs.writeFileSync(path.join(folder, "root.md"), "# Root\n");
  const note = attached(w.run("session-start.js", {}));
  assert.match(note, /hrono map \(tree "demo"\)/);
  assert.ok(note.includes(`start at ${path.join(folder, "root.md")}`));
  assert.match(note, /attached to prompts automatically/);
});
