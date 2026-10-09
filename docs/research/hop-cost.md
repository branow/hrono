# Hop-cost experiment: measuring F and s

The measurement behind the export's wide, shallow shape ([../architecture.md](../architecture.md#explore)): per-hop cost is `cost(b) = log_b(N) · (F + b·s)`, and F dominates.

## Setup

- **Stand-in for one "hop":** a single non-interactive `claude -p` invocation (model: `claude-sonnet-5`, the CLI default), with `--output-format json --tools ""` (tool schemas disabled, to keep the call closer to a pure "read summaries, pick a branch" LLM call rather than a general coding-agent call).
- **Task prompt (fixed template):** "You are navigating a hierarchical knowledge tree for a large enterprise engineering org. Below are summaries of candidate child nodes. Pick the single best match for this query: 'How do we handle payment retries after a failed charge?' Respond with only the number of the best-matching child, nothing else." followed by `b` numbered synthetic sibling summaries (~120–180 tokens each, describing fictional software subsystems — e.g. "Payment Retry Orchestrator", "Subscription Lifecycle Manager", "Fraud Signal Aggregator", etc.), plus a trailing unique `[Request ID: ...]` tag to prevent prompt-cache reuse from making repeated runs artificially cheaper.
- **Branching factors tested:** b ∈ {3, 10, 20}, 4 runs each, 12 `claude -p` invocations total.
- **Latency:** measured as actual wall-clock time around the `subprocess.run` call in Python (process start to exit), i.e. the full cost of "running the hop under this concrete tool," not just server-side model latency.
- **Tokens:** taken from the CLI's `--output-format json` response (`usage.input_tokens`, `usage.output_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens`). The CLI applies prompt caching automatically (Claude Code always marks the turn's content as cacheable), which splits the same underlying prompt differently across `input_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens` from run to run. To get a stable, comparable token count per run we use **total tokens processed** = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens` — this sum is consistent across repeated runs of the same b regardless of which cache tier absorbed the tokens (verified below: it varies by only a few tokens run-to-run at fixed b). No fallback to character-based estimation was needed — real token counts were available for every run.

## Raw per-run measurements

| b | run | wall-clock (s) | input_tokens | cache_creation | cache_read | output_tokens | total tokens | cost (USD) |
|---|-----|----------------:|-------------:|---------------:|-----------:|---------------:|-------------:|-----------:|
| 3  | 1 | 4.195 | 878 | 6224 | 3219 | 3 | 10324 | 0.04099 |
| 3  | 2 | 5.528 | 878 |  992 | 8452 | 3 | 10325 | 0.01117 |
| 3  | 3 | 3.482 | 878 |  989 | 8452 | 3 | 10322 | 0.01115 |
| 3  | 4 | 3.896 | 878 |  992 | 8452 | 3 | 10325 | 0.01117 |
| 10 | 1 | 5.130 | 878 | 2059 | 8452 | 3 | 11392 | 0.01757 |
| 10 | 2 | 2.981 | 878 | 2058 | 8452 | 3 | 11391 | 0.01756 |
| 10 | 3 | 4.058 | 878 | 2060 | 8452 | 3 | 11393 | 0.01757 |
| 10 | 4 | 4.906 | 878 | 2060 | 8452 | 3 | 11393 | 0.01757 |
| 20 | 1 | 3.365 | 878 | 3711 | 8452 | 3 | 13044 | 0.02748 |
| 20 | 2 | 4.289 | 878 | 3709 | 8452 | 3 | 13042 | 0.02747 |
| 20 | 3 | 4.361 | 878 | 3708 | 8452 | 3 | 13041 | 0.02746 |
| 20 | 4 | 4.928 | 878 | 3711 | 8452 | 3 | 13044 | 0.02748 |

(`b=3, run=1` shows a much larger `cache_creation`/lower `cache_read` split than its siblings — it was the first call of the whole run and paid a cold cache-write for the fixed Claude Code system-prompt prefix. The **total** token count is unaffected — 10324 vs. 10325/10322/10325 — confirming that total tokens is the stable metric and the fixed system-prompt overhead itself is part of realistic per-hop cost under this concrete tool.)

## Averages per b

| b  | avg wall-clock (s) | avg total tokens | avg cost (USD) |
|----|--------------------:|------------------:|----------------:|
| 3  | 4.275 | 10324.0 | 0.01862 |
| 10 | 4.269 | 11392.2 | 0.01757 |
| 20 | 4.236 | 13042.8 | 0.02747 |

## Fitted cost(b) ≈ F + s·b

Least-squares fit over the three (b, avg) points (arithmetic shown; two-point b=3→b=20 checks agree closely with the least-squares line, confirming near-perfect linearity in the token case):

**Time-based fit:**
- F ≈ **4.29 seconds**
- s ≈ **-0.002 seconds/sibling** (statistically indistinguishable from 0 at this sample size — the three averages are 4.275s, 4.269s, 4.236s, i.e. flat within run-to-run noise of roughly ±0.5-1s per single run)

**Token-based fit:**
- F ≈ **9823 tokens**
- s ≈ **160 tokens/sibling** (two-point check: (13042.8 − 10324.0) / (20 − 3) = 159.9 tokens/sibling — matches the least-squares slope almost exactly, and lines up with the ~150-180 token size of each synthetic summary plus its numbering/formatting overhead)

Arithmetic for the two-point token check:
```
s = (avg_tokens(b=20) - avg_tokens(b=3)) / (20 - 3)
  = (13042.8 - 10324.0) / 17
  = 2718.8 / 17
  ≈ 159.9 tokens per additional sibling

F = avg_tokens(b=3) - s * 3
  = 10324.0 - 159.9 * 3
  ≈ 9844.3 tokens
```
(least-squares gives F ≈ 9823.3, s ≈ 160.3 — same ballpark, small difference because least-squares uses all 3 points instead of the endpoints)

## Interpretation

Under this concrete tool (`claude -p` as a stand-in for one hop), **the fixed cost F utterly dominates the branching-dependent term s·b, in both time and tokens**: at b=20, s·b is only ~3,200 tokens against an F of ~9,800 tokens (a ratio of roughly 3:1 in F's favor), and F is essentially the *entire* wall-clock cost — going from b=3 to b=20 changed measured latency by less than the run-to-run noise. This means, for this specific harness, the cost-minimizing branching factor from the `cost(b) = log_b(N) * (F + b·s)` formula is pushed toward a **larger b**, not a smaller one: since F so heavily outweighs b·s, the `log_b(N)` term (which shrinks as b grows) is the lever that matters most, so wider trees with fewer hops beat narrow trees with many hops here. The practical takeaway is that most of the real-world cost of a hop under a CLI-driven agent tool comes from fixed per-invocation overhead (process/session start, the harness's own system prompt and tooling context — visible here as ~8,450+ cached/uncached tokens per call unrelated to the sibling list) rather than from how many sibling summaries are shown; only if F could be driven down substantially (e.g. a lighter-weight raw API call without CLI/session overhead) would the marginal per-sibling term s begin to matter enough to justify keeping branching factor small.

## Notes on methodology

- Token counts are exact, as reported by `claude -p --output-format json`'s `usage` object — no character-based estimation fallback was needed.
- Wall-clock timing includes CLI process startup, which is part of "F" as defined for this concrete harness (a real `hrono` implementation running one hop via `claude -p` would pay this same startup cost each hop).
- A unique per-run `[Request ID: ...]` tag was appended to each prompt to prevent the CLI's automatic prompt caching from making later repeated runs of the same b artificially cheap/fast, which would have biased the per-b averages.
