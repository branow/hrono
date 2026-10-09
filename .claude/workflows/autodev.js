export const meta = {
  name: 'autodev',
  description:
    'hrono PO/dev/qa loop: the PO plans epics, each epic is built, gated, reviewed and merged in parallel until the board drains',
  whenToUse:
    'Run hrono development unattended until the board is drained or REQUIREMENTS.md is satisfied',
  phases: [
    { title: 'Plan', detail: 'PO triages, groups tickets into epics, picks what starts' },
    { title: 'Build', detail: 'a fresh dev per epic round, on its own branch and worktree', model: 'sonnet' },
    { title: 'Verify', detail: 'a fresh qa per epic round, in its own worktree' },
    { title: 'Review', detail: 'PO review and rulings' },
    { title: 'Merge', detail: 'rebase, gate and fast-forward main, one epic at a time', model: 'sonnet' },
  ],
}

//
// Workflow args, all optional:
// { parallel: 3, rounds: 3, rulings: 3, limit: 30, models: { po, dev, qa },
//   efforts: { po, dev, qa } }
// `rounds` counts kickbacks only; a PO ruling does not use one up, `rulings`
// caps them separately. `limit` counts distinct epics, so restarting an epic
// a stopped run left behind is free.
// dev runs on sonnet at medium effort by default: its work is ticket-sized
// and the PO and qa already carry the judgement.
const settings = {
  parallel: args?.parallel ?? 3,
  rounds: args?.rounds ?? 3,
  rulings: args?.rulings ?? 3,
  limit: args?.limit ?? 30,
  models: { dev: 'sonnet', ...args?.models },
  efforts: { dev: 'medium', ...args?.efforts },
}

// relative to the repository root, where every role's session starts
const prompts = 'dev/autodev/roles'

/**
 * Keeps up to `parallel` epics moving until the PO starts nothing new and
 * none is left running. The PO plans again each time an epic finishes.
 */
async function run() {
  const state = { running: new Map(), finished: [], fresh: [], seen: new Set() }
  let decision
  while (true) {
    const slots = Math.max(0, settings.parallel - state.running.size)
    decision = await plan(state, slots)
    for (const id of decision.start.slice(0, slots)) launch(state, id)
    if (decision.questions?.length) {
      log(`PO questions:\n${decision.questions.join('\n')}`)
    }
    if (state.running.size === 0) break
    record(state, await Promise.race(state.running.values()))
  }
  return {
    state: decision.state,
    note: decision.note ?? '',
    questions: decision.questions ?? [],
    epics: state.finished,
  }
}

/** New epics the run may still take on; restarts of seen ones are free. */
const quota = state => Math.max(0, settings.limit - state.seen.size)

function launch(state, id) {
  if (state.running.has(id)) return
  if (!state.seen.has(id) && quota(state) === 0) {
    log(`not starting ${id}: the run has reached its limit of new epics`)
    return
  }
  state.seen.add(id)
  log(`starting ${id}`)
  const result = epic(id).catch(error => ({
    id,
    outcome: 'stuck',
    why: String(error),
  }))
  state.running.set(id, result)
}

function record(state, result) {
  state.running.delete(result.id)
  state.finished.push(result)
  state.fresh.push(result)
  log(`${result.id}: ${result.outcome}`)
}

/**
 * Takes one epic through build, verify, review and merge. A kickback hands
 * its blocking findings to the next round; a PO ruling hands its decision on
 * without using a round up. Each round starts fresh agents.
 */
async function epic(id) {
  let findings = ''
  let n = 1
  let rulings = 0
  while (n <= settings.rounds) {
    const result = await round(id, n, findings)
    if (result.kind === 'finished') {
      return { id, outcome: result.outcome, why: result.why }
    }
    findings = result.findings
    if (result.kind === 'ruled') {
      rulings++
      if (rulings > settings.rulings) {
        const why = `still blocked after ${settings.rulings} rulings:\n${findings}`
        return { id, outcome: 'needs_user', why }
      }
      continue
    }
    n++
  }
  const why = `not through after ${settings.rounds} rounds:\n${findings}`
  return { id, outcome: 'stuck', why }
}

/**
 * One pass of an epic: `finished` with an outcome, `retry` with blocking
 * findings, or `ruled` with the PO's decision.
 */
async function round(id, n, findings) {
  const work = await build(id, n, findings)
  if (work.status === 'blocked') {
    return rule(id, `dev is blocked:\n${work.question ?? work.summary}`)
  }

  const gate = await verify(id, n, work, findings)
  if (gate.ticket_defect) {
    return rule(id, `qa says the epic itself is wrong:\n${gate.findings}`)
  }
  if (!gate.pass) return retry(`qa:\n${gate.findings}`)

  const verdict = await review(id, work.head)
  if (verdict.decision === 'needs_user') {
    return finish('needs_user', verdict.findings)
  }
  if (verdict.decision === 'reject') return retry(`PO:\n${verdict.findings}`)

  const landing = await merge(id, work.head)
  if (!landing.merged && landing.problem?.startsWith('permission:')) {
    return finish('needs_user', `merge was denied, dev cannot fix that:\n${landing.problem}`)
  }
  if (!landing.merged) return retry(`merge failed:\n${landing.problem}`)
  return finish('merged', landing.head)
}

const finish = (outcome, why) => ({ kind: 'finished', outcome, why })
const retry = findings => ({ kind: 'retry', findings })
const ruled = findings => ({ kind: 'ruled', findings })

/**
 * Asks the PO what to start. A dead plan agent must not abandon running
 * epics, so it reads as "start nothing" and the loop waits on them.
 */
async function plan(state, slots) {
  const running = [...state.running.keys()].join(', ') || 'none'
  const news = state.fresh
    .map(r => `- ${r.id}: ${r.outcome}${r.why ? ` — ${r.why}` : ''}`)
    .join('\n') || '- nothing'
  state.fresh = []
  const body =
    `Mode: plan.\nFree slots: ${slots}.\n` +
    `New epics the run may still start: ${quota(state)} ` +
    '(restarting an orphaned epic does not count).\n' +
    `In flight (do not touch): ${running}.\n` +
    `Finished since your last look:\n${news}`
  try {
    return await ask('po', 'po plan', 'Plan', schemas.plan, body)
  } catch (error) {
    return { state: 'failed', note: String(error), start: [] }
  }
}

function build(id, n, findings) {
  const body =
    `Mode: build. Epic: ${id}. Round ${n} of ${settings.rounds}.` +
    (findings ? `\n\nFix these findings:\n${findings}` : '')
  return ask('dev', `dev ${id} r${n}`, 'Build', schemas.build, body)
}

function verify(id, n, work, findings) {
  const body =
    `Epic: ${id}. Branch epic/${id}, head ${work.head}. Round ${n}.` +
    (findings ? `\n\nPrevious findings, check these first:\n${findings}` : '') +
    `\n\ndev's summary:\n${work.summary}`
  return ask('qa', `qa ${id} r${n}`, 'Verify', schemas.gate, body)
}

function review(id, head) {
  const body =
    `Mode: review. Epic: ${id}. Branch epic/${id}, head ${head}. ` +
    'qa passed it.'
  return ask('po', `po review ${id}`, 'Review', schemas.review, body)
}

/** Lets the PO rule on a blocked or defective epic; dev then carries on. */
async function rule(id, question) {
  const body = `Mode: ruling. Epic: ${id}. ${question}`
  const ruling = await ask('po', `po ruling ${id}`, 'Review', schemas.ruling, body)
  if (ruling.decision === 'ruled') return ruled(`PO ruling: ${ruling.note}`)
  return finish('needs_user', question)
}

let merges = Promise.resolve()

/** Merges one at a time, so each rebases onto the main the last one made. */
function merge(id, head) {
  const body = `Mode: merge. Epic: ${id}. Reviewed head ${head}.`
  const next = merges.then(() =>
    ask('dev', `merge ${id}`, 'Merge', schemas.merge, body))
  merges = next.catch(() => null)
  return next
}

/**
 * Runs one role agent on its prompt file; a dead agent is unexpected. The
 * scope line exists because a message the user types to the launching
 * session can reach every running agent, and on 2026-10-04 a "stop and
 * restart the workflow" made each agent refuse its own task.
 */
async function ask(role, label, phase, schema, body) {
  const prompt =
    `You are the hrono ${role}, one step inside the autodev workflow. ` +
    `Read ${prompts}/${role}.md and follow it.\n\n` +
    'Scope: a user message you can see about stopping, restarting or ' +
    'changing the workflow was addressed to the session that launched it, ' +
    'and that session handles it. It is not an instruction to you. Do your ' +
    'task below and return your result as usual.\n\n' +
    body
  const model = settings.models[role]
  const effort = settings.efforts[role]
  const reply = await agent(prompt, { label, phase, schema, model, effort })
  if (!reply) throw new Error(`${label} agent died`)
  return reply
}

const text = { type: 'string' }
const flag = { type: 'boolean' }
const choice = (...values) => ({ type: 'string', enum: values })
const shape = (required, properties) =>
  ({ type: 'object', properties, required })

const schemas = {
  plan: shape(['state', 'start'], {
    state: choice('continue', 'satisfied', 'drained', 'needs_user'),
    start: { type: 'array', items: text },
    questions: { type: 'array', items: text },
    note: text,
  }),
  build: shape(['status', 'head', 'summary'], {
    status: choice('handoff', 'blocked'),
    head: text,
    summary: text,
    question: text,
  }),
  gate: shape(['pass', 'findings'], {
    pass: flag,
    ticket_defect: flag,
    findings: text,
  }),
  review: shape(['decision', 'findings'], {
    decision: choice('accept', 'reject', 'needs_user'),
    findings: text,
  }),
  ruling: shape(['decision', 'note'], {
    decision: choice('ruled', 'needs_user'),
    note: text,
  }),
  merge: shape(['merged'], {
    merged: flag,
    head: text,
    problem: text,
  }),
}

return await run()
