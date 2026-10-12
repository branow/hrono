// @ts-check
"use strict";
// The hrono CLI, the one way the hooks reach a server. A call returns a state
// rather than throwing: a server that is down or slow is an expected outcome
// the caller decides about, not an error.

const { spawnSync } = require("node:child_process");

const RECALL_TIMEOUT_MS = 15000;

/**
 * @typedef {object} Hit
 * @property {"source" | "summary"} kind
 * @property {string} body
 * @property {string} [path]    the source file, relative to its source
 * @property {string} [source]  the source it was read from
 * @property {number} [topic]   the topic a brief belongs to
 * @property {string} [header]  hrono's internal address
 */

/**
 * @typedef {{ ok: true, hits: Hit[] } | { ok: false, reason: string }} Recalled
 */

/**
 * The map pages that answer ``question``, from ``tree``: one hit per leaf
 * topic, each the passage that put the page there.
 * @param {string} bin
 * @param {string} tree
 * @param {string} question
 * @param {number} limit
 * @returns {Recalled}
 */
function recall(bin, tree, question, limit) {
  const run = spawnSync(
    bin,
    ["recall", tree, question, "--json", "--pages", "--limit", String(limit)],
    { encoding: "utf8", timeout: RECALL_TIMEOUT_MS },
  );
  if (run.status !== 0) return { ok: false, reason: failure(run) };
  try {
    const hits = JSON.parse(run.stdout).hits;
    return Array.isArray(hits) ? { ok: true, hits } : { ok: false, reason: "no hits field" };
  } catch {
    return { ok: false, reason: "unreadable reply" };
  }
}

/** @param {import("node:child_process").SpawnSyncReturns<string>} run */
function failure(run) {
  if (run.error) return run.error.message;
  return (run.stderr || run.stdout || `exit ${run.status}`).trim();
}

module.exports = { recall };
