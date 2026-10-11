// @ts-check
"use strict";
// The hook boundary: what Claude Code sends a hook on stdin, and how a hook
// hands text back to the model. A hook must never fail the event it runs on,
// so anything unexpected ends in silence, not an error in front of the user.

const fs = require("node:fs");

/**
 * @typedef {object} Input
 * @property {string} cwd
 * @property {string} prompt  empty for events without one
 */

/** @returns {Input} */
function input() {
  try {
    const data = JSON.parse(fs.readFileSync(0, "utf8") || "{}");
    return {
      cwd: typeof data.cwd === "string" ? data.cwd : process.cwd(),
      prompt: typeof data.prompt === "string" ? data.prompt : "",
    };
  } catch {
    return { cwd: process.cwd(), prompt: "" };
  }
}

/**
 * Run a hook: read its input, write the context it returns, swallow failure.
 * @param {"SessionStart" | "UserPromptSubmit"} event
 * @param {(input: Input) => string | null} produce
 */
function run(event, produce) {
  try {
    const context = produce(input());
    if (context === null) return;
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: event, additionalContext: context },
      }),
    );
  } catch {
    // never block a prompt or a session over the plugin
  }
}

module.exports = { run };
