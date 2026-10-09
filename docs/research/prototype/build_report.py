"""Build a single-page HTML report of all recorded summarization experiments.

Scans everything under .hrono/summarization-experiments/ — every cluster-*
directory, every experiment round — and renders each experiment as a
self-contained pipeline: every LLM call that produced its result (map-stage
condensations for condensed-input experiments, then the final summary call),
each with the full request, full response, duration and cost. Writes
.hrono/summarization-experiments/report.html, fully self-contained.

Usage: uv run python build_report.py
"""

import html
import json
from dataclasses import dataclass
from pathlib import Path

HRONO_DIR = Path(".hrono")
SAMPLES_DIR = HRONO_DIR / "summarization-samples"
EXPERIMENTS_DIR = HRONO_DIR / "summarization-experiments"
MAP_CACHE_DIR = EXPERIMENTS_DIR / "map-cache"
REPORT_PATH = EXPERIMENTS_DIR / "report.html"


def main() -> None:
    build_report()


def build_report() -> None:
    """Scan all recorded experiment data and (re)write report.html."""
    clusters = load_clusters()
    REPORT_PATH.write_text(render_report(clusters))
    experiments = sum(len(c.experiments) for c in clusters)
    print(f"report: {REPORT_PATH} ({REPORT_PATH.stat().st_size // 1024}KB, "
          f"{len(clusters)} clusters, {experiments} experiments)")


# --- Data loading -------------------------------------------------------------

@dataclass
class StepCall:
    purpose: str
    model: str
    prompt: str
    response: str
    duration_ms: int
    cost_usd: float


@dataclass
class ExperimentCall:
    name: str
    model: str
    prompt_key: str | None
    condensed: bool
    prompt: str | None  # None: round-1 run, prompt was not recorded
    response: str
    duration_ms: int | None  # sum across calls when the experiment is multi-step
    cost_usd: float | None
    calls: list[StepCall]  # execution order; empty for pre-"calls" rounds


@dataclass
class MapCall:
    chunk_label: str
    model: str
    prompt: str
    response: str
    duration_ms: int
    cost_usd: float


@dataclass
class ClusterReport:
    id: str
    input_note: str  # e.g. "26 raw chunks (89KB)"
    experiments: list[ExperimentCall]
    map_calls: list[MapCall]  # in chunk order; shared by condensed experiments


def load_clusters() -> list[ClusterReport]:
    clusters = []
    for cluster_dir in sorted(EXPERIMENTS_DIR.glob("cluster-*"),
                              key=lambda p: int(p.name.split("-")[1])):
        cluster_id = cluster_dir.name.removeprefix("cluster-")
        clusters.append(ClusterReport(
            id=cluster_id,
            input_note=describe_raw_input(cluster_id),
            experiments=[load_experiment(p) for p in sorted(cluster_dir.glob("*.meta.json"))],
            map_calls=load_map_calls(cluster_id),
        ))
    return clusters


def load_experiment(meta_path: Path) -> ExperimentCall:
    meta = json.loads(meta_path.read_text())
    summary_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".md"))
    return ExperimentCall(
        name=meta["experiment"],
        model=meta.get("model", "?"),
        prompt_key=meta.get("prompt_key"),
        condensed=bool(meta.get("condensed_input")),
        prompt=meta.get("prompt"),
        response=meta.get("response")
                 or (summary_path.read_text() if summary_path.exists() else ""),
        duration_ms=meta.get("duration_ms"),
        cost_usd=meta.get("cost_usd"),
        calls=[StepCall(**c) for c in meta.get("calls", [])],
    )


def load_map_calls(cluster_id: str) -> list[MapCall]:
    """Recorded condensation calls for this cluster's chunks, in chunk order.

    The map cache is keyed by chunk content hash, so the cluster's sample
    metadata is the bridge from cluster to its map-call records.
    """
    meta_path = SAMPLES_DIR / f"cluster-{cluster_id}" / "meta.json"
    if not meta_path.exists():
        return []
    calls = []
    for member in json.loads(meta_path.read_text())["members"]:
        record_path = MAP_CACHE_DIR / f"{member['hash']}.call.json"
        if record_path.exists():
            calls.append(MapCall(**json.loads(record_path.read_text())))
    return calls


def describe_raw_input(cluster_id: str) -> str:
    chunks_dir = SAMPLES_DIR / f"cluster-{cluster_id}" / "chunks"
    if not chunks_dir.exists():
        return "raw chunks (samples not available)"
    paths = list(chunks_dir.iterdir())
    total_kb = sum(p.stat().st_size for p in paths) // 1024
    return f"{len(paths)} raw chunks ({total_kb}KB)"


# --- Page rendering -----------------------------------------------------------

def render_report(clusters: list[ClusterReport]) -> str:
    total = sum(cluster_cost(c) for c in clusters)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Summarization experiments</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Summarization experiments</h1>
<p class="subtitle">Every recorded LLM call, per experiment: what was sent, what came
back, how long it took and what it cost. Total recorded cost across all clusters:
<strong>{fmt_cost(total)}</strong>.</p>
<div class="controls">
<button type="button" onclick="setAll(true)">Expand all</button>
<button type="button" onclick="setAll(false)">Collapse all</button>
</div>
{render_nav(clusters)}
{"".join(render_cluster(c) for c in clusters)}
</main>
<script>{JS}</script>
</body>
</html>
"""


def render_nav(clusters: list[ClusterReport]) -> str:
    items = "\n".join(
        f"<li><a href='#{cluster_anchor(c.id)}'>cluster {c.id}</a> "
        f"<span class='nav-note'>({c.input_note})</span><ul>"
        + "".join(f"<li><a href='#{exp_anchor(c.id, e.name)}'>{esc(e.name)}</a></li>"
                  for e in c.experiments)
        + "</ul></li>"
        for c in clusters
    )
    return f"<nav><h2>Index</h2><ul>{items}</ul></nav>"


def render_cluster(cluster: ClusterReport) -> str:
    sections = "".join(render_experiment(cluster, e) for e in cluster.experiments)
    return f"""
<details class="cluster" id="{cluster_anchor(cluster.id)}">
<summary><span class="s-name">Cluster {cluster.id}</span><span class="s-meta">{esc(cluster.input_note)} &middot; {len(cluster.experiments)} experiments &middot; {fmt_cost(cluster_cost(cluster))}</span></summary>
<div class="body">
{render_overview(cluster)}
{sections}
</div>
</details>
"""


def render_overview(cluster: ClusterReport) -> str:
    rows = "\n".join(
        f"<tr><td><a href='#{exp_anchor(cluster.id, e.name)}'>{esc(e.name)}</a></td>"
        f"<td>{esc(e.model)}</td>"
        f"<td>{'condensed' if e.condensed else 'raw'}</td>"
        f"<td class='num'>{fmt_size(len(e.prompt)) if e.prompt else '&mdash;'}</td>"
        f"<td class='num'>{fmt_size(len(e.response))}</td>"
        f"<td class='num'>{fmt_duration(e.duration_ms)}</td>"
        f"<td class='num'>{fmt_cost(e.cost_usd)}</td></tr>"
        for e in cluster.experiments
    )
    map_cost = sum(c.cost_usd for c in cluster.map_calls)
    map_row = (
        f"<tr class='total'><td colspan='6'>Map stage ({len(cluster.map_calls)} haiku "
        f"calls, cached &mdash; shared by the condensed experiments, counted once)</td>"
        f"<td class='num'>{fmt_cost(map_cost)}</td></tr>"
        if cluster.map_calls else ""
    )
    return f"""
<div class="table-wrap">
<table>
<thead><tr><th>Experiment</th><th>Model</th><th>Input</th><th>Prompt</th>
<th>Response</th><th>Duration</th><th>Cost</th></tr></thead>
<tbody>
{rows}
{map_row}
<tr class="grand-total"><td colspan="6">Cluster total</td>
<td class="num">{fmt_cost(cluster_cost(cluster))}</td></tr>
</tbody>
</table>
</div>
"""


# --- Experiment pipeline rendering --------------------------------------------

def render_experiment(cluster: ClusterReport, e: ExperimentCall) -> str:
    map_stage = render_map_stage(cluster) if e.condensed else ""
    own_calls = render_step_calls(e) if e.calls else render_single_call(cluster, e)
    return f"""
<details class="experiment" id="{exp_anchor(cluster.id, e.name)}">
<summary><span class="s-name">{esc(e.name)}</span><span class="s-meta">{esc(e.model)} &middot; {"condensed" if e.condensed else "raw"} &middot; {fmt_cost(e.cost_usd)} &middot; {fmt_duration(e.duration_ms)}</span></summary>
<div class="body">
<p class="pipeline">{experiment_intro(cluster, e)}{prompt_key_note(e)}</p>
{render_metrics(e)}
{map_stage}
{own_calls}
</div>
</details>
"""


def experiment_intro(cluster: ClusterReport, e: ExperimentCall) -> str:
    input_part = (
        f"input: {len(cluster.map_calls)} haiku condensations from the map stage below"
        if e.condensed else
        f"input: {esc(cluster.input_note)}, sent verbatim"
    )
    calls_part = (
        f"{len(e.calls)}-step pipeline on <strong>{esc(e.model)}</strong>: "
        + " &rarr; ".join(esc(c.purpose) for c in e.calls)
        if e.calls else
        f"one summary call to <strong>{esc(e.model)}</strong>"
    )
    return f"{input_part} &middot; {calls_part}"


def render_step_calls(e: ExperimentCall) -> str:
    total = len(e.calls)
    heading = "Pipeline calls" if total > 1 else "Summary call"
    entries = "\n".join(
        f"""<details class="call">
<summary><span class="s-name">Call {i} of {total} &mdash; {esc(c.purpose)} ({esc(c.model)})</span><span class="s-meta">{fmt_duration(c.duration_ms)} &middot; {fmt_cost(c.cost_usd)}</span></summary>
<div class="body">
<h5>Request ({fmt_size(len(c.prompt))})</h5>
<pre class="prompt">{esc(c.prompt)}</pre>
<h5>Response ({fmt_size(len(c.response))})</h5>
<pre class="response">{esc(c.response)}</pre>
</div>
</details>"""
        for i, c in enumerate(e.calls, 1)
    )
    return f"<h4>{heading} (in execution order)</h4>\n{entries}"


def render_single_call(cluster: ClusterReport, e: ExperimentCall) -> str:
    n = len(cluster.map_calls)
    step = f"Call {n + 1} of {n + 1}" if e.condensed and n else "Single call"
    return f"""<h4>{step} &mdash; final summary ({esc(e.model)})</h4>
{render_prompt(e.prompt)}
<h5>Response</h5>
<pre class="response">{esc(e.response)}</pre>"""


def render_map_stage(cluster: ClusterReport) -> str:
    if not cluster.map_calls:
        return ("<h4>Call 1 &mdash; map stage</h4>"
                "<p class='not-recorded'>map-stage calls not recorded for this cluster</p>")
    entries = "\n".join(render_map_call(c) for c in cluster.map_calls)
    map_cost = sum(c.cost_usd for c in cluster.map_calls)
    return f"""
<h4>Calls 1&ndash;{len(cluster.map_calls)} &mdash; map stage: one haiku condensation per chunk</h4>
<p class="cache-note">These calls are cached by chunk hash and shared across every
condensed experiment in this cluster; they ran once, {fmt_cost(map_cost)} in total.</p>
{entries}
"""


def render_map_call(c: MapCall) -> str:
    return f"""<details class="call">
<summary><span class="s-name">{esc(c.chunk_label)}</span><span class="s-meta">{esc(c.model)} &middot; {fmt_duration(c.duration_ms)} &middot; {fmt_cost(c.cost_usd)}</span></summary>
<div class="body">
<h5>Request ({fmt_size(len(c.prompt))})</h5>
<pre class="prompt">{esc(c.prompt)}</pre>
<h5>Response ({fmt_size(len(c.response))})</h5>
<pre class="response">{esc(c.response)}</pre>
</div>
</details>"""


def render_prompt(prompt: str | None) -> str:
    if prompt is None:
        return "<p class='not-recorded'>prompt not recorded (round 1)</p>"
    return f"""<details>
<summary><span class="s-name">Request sent ({fmt_size(len(prompt))})</span></summary>
<div class="body">
<pre class="prompt">{esc(prompt)}</pre>
</div>
</details>"""


def render_metrics(e: ExperimentCall) -> str:
    items = [("model", e.model),
             ("input", "condensed" if e.condensed else "raw"),
             *([("calls", len(e.calls))] if e.calls else []),
             ("duration", fmt_duration(e.duration_ms)),
             ("cost", fmt_cost(e.cost_usd)),
             ("prompt", fmt_size(len(e.prompt)) if e.prompt else "not recorded"),
             ("response", fmt_size(len(e.response)))]
    cells = "".join(
        f"<div><span class='label'>{k}</span><span class='value'>{v}</span></div>"
        for k, v in items
    )
    return f"<div class='metrics'>{cells}</div>"


def prompt_key_note(e: ExperimentCall) -> str:
    return f" &middot; prompt: <code>{esc(e.prompt_key)}</code>" if e.prompt_key else ""


# --- Formatting helpers -------------------------------------------------------

def cluster_cost(cluster: ClusterReport) -> float:
    return (sum(e.cost_usd or 0 for e in cluster.experiments)
            + sum(c.cost_usd for c in cluster.map_calls))


def esc(text: str) -> str:
    return html.escape(text)


def cluster_anchor(cluster_id: str) -> str:
    return f"cluster-{cluster_id}"


def exp_anchor(cluster_id: str, name: str) -> str:
    return f"c{cluster_id}-{name.replace('_', '-')}"


def fmt_size(chars: int) -> str:
    return f"{chars / 1024:.1f}KB" if chars >= 1024 else f"{chars} chars"


def fmt_duration(ms: int | None) -> str:
    return f"{ms / 1000:.1f}s" if ms is not None else "&mdash;"


def fmt_cost(usd: float | None) -> str:
    return f"${usd:.4f}" if usd is not None else "&mdash;"


JS = """
function setAll(open) {
  document.querySelectorAll('details').forEach(function (d) { d.open = open; });
}
function openTarget() {
  var el = document.getElementById(location.hash.slice(1));
  if (!el) return;
  for (var d = el.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) {
    d.open = true;
  }
  el.scrollIntoView();
}
window.addEventListener('hashchange', openTarget);
openTarget();
"""

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #fafaf8; color: #1f2328;
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 24px 80px; }
h1 { font-size: 1.6em; margin: 0 0 4px; }
h2 { font-size: 1.3em; margin: 0 0 12px; }
h4 { font-size: 0.95em; margin: 24px 0 8px; }
h5 { font-size: 0.8em; margin: 16px 0 8px; color: #57606a; text-transform: uppercase; letter-spacing: 0.04em; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.9em;
  background: #efede7; padding: 1px 4px; border-radius: 3px; }
a { color: #0959a8; }
.subtitle { color: #57606a; margin: 0 0 24px; }
nav { background: #fff; border: 1px solid #e2e0da; border-radius: 6px;
  padding: 16px; margin: 0 0 32px; }
nav h2 { font-size: 1em; margin: 0 0 8px; }
nav ul { margin: 4px 0; padding-left: 24px; }
nav .nav-note { color: #85806f; font-size: 0.9em; }
.controls { margin: 0 0 16px; display: flex; gap: 8px; }
.controls button { font: inherit; font-size: 0.88em; padding: 5px 12px; cursor: pointer;
  background: #fff; border: 1px solid #d8d5cd; border-radius: 6px; color: #1f2328; }
.controls button:hover { background: #f3f1ec; }

details { background: #fff; border: 1px solid #e2e0da; border-radius: 6px;
  margin: 0 0 8px; min-width: 0; }
summary { display: flex; align-items: baseline; gap: 12px;
  cursor: pointer; padding: 8px 12px; font-weight: 600; font-size: 0.92em;
  list-style: none; min-width: 0; }
summary::-webkit-details-marker { display: none; }
summary::before { content: "\\25B8"; flex: none; width: 1em; color: #9a958a; }
details[open] > summary::before { content: "\\25BE"; }
summary:hover { background: #f7f6f2; }
.s-name { flex: 0 1 auto; min-width: 0; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.s-meta { flex: none; margin-left: auto; white-space: nowrap;
  font-weight: 400; color: #85806f; font-size: 0.9em; font-variant-numeric: tabular-nums; }
details > .body { padding: 8px 12px 12px 28px; min-width: 0; }
details.cluster { margin: 0 0 16px; border-color: #d8d5cd; }
details.cluster > summary { font-size: 1.1em; padding: 12px 16px; }
details.cluster > .body { padding: 8px 16px 16px 16px; }
details.experiment > summary { font-size: 1em; }

.table-wrap { overflow-x: auto; margin: 0 0 16px; border: 1px solid #e2e0da;
  border-radius: 6px; background: #fff; }
table { border-collapse: collapse; width: 100%; font-size: 0.95em; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #eceae4;
  white-space: nowrap; }
td:first-child, th:first-child { white-space: normal; }
th { background: #f3f1ec; font-weight: 600; }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.total td { color: #57606a; background: #faf9f6; white-space: normal; }
tr.grand-total td { font-weight: 700; background: #f3f1ec; }

.pipeline { color: #57606a; margin: 0 0 16px; font-size: 0.95em; }
.cache-note { color: #7a5c1e; background: #fdf6e5; border: 1px solid #ecd9b4;
  border-radius: 5px; padding: 6px 10px; font-size: 0.9em; margin: 0 0 12px; }
.not-recorded { color: #85806f; font-style: italic; background: #f6f5f1;
  border: 1px dashed #dcd9d1; border-radius: 5px; padding: 6px 10px; font-size: 0.9em; }
.metrics { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 16px; }
.metrics div { background: #faf9f6; border: 1px solid #e2e0da; border-radius: 6px;
  padding: 6px 12px; display: flex; flex-direction: column; min-width: 96px; }
.metrics .label { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.05em; color: #85806f; }
.metrics .value { font-weight: 600; font-variant-numeric: tabular-nums; }

pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82em;
  line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere;
  background: #f6f5f1; border: 1px solid #eae8e1; border-radius: 6px;
  padding: 12px; margin: 0 0 8px; overflow: auto; max-height: 60vh; max-width: 100%; }
pre.response { background: #fdfdfc; }
"""


if __name__ == "__main__":
    main()
