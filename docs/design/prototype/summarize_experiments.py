"""Run cluster-summarization prompt experiments over the sample clusters.

Generates one summary per (approach x size budget) for a sample cluster in
.hrono/summarization-samples/, using the `claude` CLI (headless `claude -p`)
as the LLM backend, and saves every summary plus run metadata to
.hrono/summarization-experiments/cluster-<id>/ for manual evaluation.

Usage: uv run python summarize_experiments.py [cluster_id ...]
"""

import asyncio
import hashlib
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from build_report import build_report
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

HRONO_DIR = Path(".hrono")
SAMPLES_DIR = HRONO_DIR / "summarization-samples"
EXPERIMENTS_DIR = HRONO_DIR / "summarization-experiments"
MAP_CACHE_DIR = EXPERIMENTS_DIR / "map-cache"

MAP_MODEL = "haiku"
PARALLEL_CALLS = 4

# All prompts ever tried, kept for history. The active EXPERIMENTS matrix below
# selects which ones actually run.
PROMPTS = {
    # ---- round 1: literature baselines ------------------------------------
    # RAPTOR-style minimal prompt with a size budget.
    "r1-naive": """\
Write a summary of the following group of files/chunks from a codebase, including
as many key details as possible. Keep the summary under {size} tokens. Output only
the summary, nothing else.""",

    # GraphRAG-style: fixed sections, entity-rich title, per-chunk references,
    # grounding rules. (Round-1 "two-stage" = this prompt over condensed input.)
    "r1-structured": """\
You are building a node summary for a knowledge tree over a codebase. A group of
related files/chunks (one cluster) is given below. An AI agent will later read ONLY
your summary, next to summaries of sibling clusters, to decide whether the answer to
its question is inside this cluster. Write the summary for that routing decision.

Produce exactly this markdown structure:

# <title>
A short but specific title naming the key entities (module names, class names,
config domains) that represent this cluster.

## Overview
2-4 sentences: what this group of files is, what it does as a whole, and what kinds
of questions it can answer. This is the abstraction - find the common point, do not
list the files.

## References
One line per chunk, in the given order:
- `<chunk label>` - what this specific chunk contains, with the concrete names
  (functions, classes, keys, endpoints) that appear in it.

Grounding rules: mention only things actually present in the given content - do not
make anything up. Prefer concrete identifiers over vague descriptions. Keep the
whole output under {size} tokens; if the reference list would exceed the budget,
group near-identical chunks into one line.""",

    # ---- round 2: freeform layered ----------------------------------------
    # The naive-1500 shape the manual review preferred. REJECTED: names
    # code-specific layers (controller/DTO/mapper...), but clusters can hold any
    # content type. Kept for history.
    "r2-freeform": """\
Summarize the following group of related files/chunks from a codebase. The summary
is a node in a knowledge tree: a reader (human or AI agent) uses it to understand
what this part of the system is and does, without opening the files.

Guidelines:
- Start by stating what this group implements as a whole, and the language,
  framework, and technologies involved.
- Identify the structural patterns actually present (e.g. controller, DTOs, mapper,
  model, repository, service - whatever the group really contains) and organize the
  summary by them, one section per pattern/layer.
- Describe each part with concrete identifiers: class names, endpoints, methods,
  config keys, validation rules, exceptions.
- Tests deserve only a brief mention: what is covered and how (unit/integration),
  not test-by-test detail.
- Mention only what is actually present in the content - do not invent anything.

Output only the summary in markdown, nothing else.""",

    # ---- round 3: content-agnostic variants (ACTIVE) ----------------------
    # A cluster can hold code, config, translations, prose - the prompt must not
    # assume any of them.
    "plain": """\
Write a summary of the following group of related content chunks, including as many
key details as possible. Output only the summary, nothing else.""",

    "adaptive": """\
Summarize the following group of related content chunks. The summary is a node in a
knowledge tree: a reader (human or AI agent) uses it to understand what this group
is and contains, without opening the chunks.

Guidelines:
- Start by stating what this group is as a whole and what domain/technology/format
  it belongs to, if any is apparent.
- Look at the content and identify the natural groupings or patterns actually
  present in it - whatever they are. Organize the summary by them, one section per
  grouping. Choose the structure that fits THIS content; do not force one.
- Describe each part with the concrete names and terms that appear in it.
- If many chunks are near-identical or repetitive, describe the pattern once and
  note the variation, instead of describing each.
- Mention only what is actually present in the content - do not invent anything.

Output only the summary in markdown, nothing else.""",

    "routing": """\
The chunks below form one group of related content. Write the text that would let
someone decide, without opening the chunks, whether what they are looking for is
inside this group: what it is, what it contains, what questions it can answer.
Use the concrete names and terms from the content. Choose whatever length and
structure fits the content best. Do not invent anything. Output only the summary.""",

    # ---- round 4: multi-step and structured approaches (ACTIVE) -----------
    # Second pass of a refinement cycle: check the draft against the content.
    "refine": """\
Below is a draft summary of a group of content chunks, followed by the full content
it summarizes. Produce an improved final version of the summary: add important facts
the draft missed, remove or correct anything not literally supported by the content,
merge redundant points, and keep whatever structure fits the content. Output only
the improved summary in markdown.

DRAFT:
{draft}

FULL CONTENT:""",

    # Step 1 of outline-then-write: a compact inventory, no prose.
    "outline": """\
List the natural groupings present in the following content chunks. Output a compact
outline only, no prose: one line per grouping with a short name, the chunk labels
that belong to it, and the most important concrete names/terms appearing in it.""",

    # Step 2 of outline-then-write: prose from the outline, grounded in content.
    "outline-write": """\
Using the outline below (derived from the same content) as the structure, summarize
the content chunks: start with what the group is as a whole, then one section per
outline grouping, describing each with the concrete names and terms from the
content. Do not invent anything. Output only the summary in markdown.

OUTLINE:
{outline}

FULL CONTENT:""",

    # Machine-usable node record instead of free markdown.
    "json": """\
Summarize the following group of related content chunks as a single JSON object with
exactly this shape:
{"title": string, "overview": string, "groups": [{"name": string, "description":
string, "chunks": [chunk labels belonging to it]}], "key_terms": [string]}
"overview" states what the group is as a whole. Mention only what is present in the
content - do not invent anything. Output only valid JSON, nothing else.""",

    # ---- round 5: routing-oriented additions (ACTIVE) ----------------------
    # Contrastive/sibling-aware: routing is a comparison among siblings
    # (LlamaIndex TREE_SELECT shows child summaries side by side), so the node
    # text is written WITH the siblings' existing summaries in view, to be
    # discriminative rather than merely descriptive. Coupling cost: a sibling
    # change can stale this summary - acceptable if regenerated from cached
    # condensations. Runs over condensed input like the current best.
    "contrast": """\
Summarize the following group of related content chunks. The summary is a node in a
knowledge tree: an AI agent reads it NEXT TO the summaries of the sibling nodes
(included below for context) and must decide which single node to open for its
question. Optimize the summary for that comparison.

Guidelines:
- Describe what THIS group is and contains, organized by the natural groupings
  actually present in the content, using the concrete names and terms from it.
- Where this group could be confused with a sibling (same domain, technology, or
  file family), make the distinction explicit: what is here versus what is in the
  sibling instead.
- End with a short "Not here:" list - things a reader might expect in this group
  that actually live in a sibling, naming that sibling.
- Sibling content may appear only inside those distinction notes, never described
  as part of this group. Mention only what is actually present in the given
  content - do not invent anything.

Output only the summary in markdown, nothing else.""",

    # Question-guided: anticipate the queries the routing agent will carry; the
    # summary ends with an explicit "Answers questions like:" section the agent
    # can match its question against directly.
    "questions": """\
Summarize the following group of related content chunks. The summary is a node in a
knowledge tree: an AI agent reads it, next to sibling summaries, to decide whether
the answer to its question is inside this group.

Work question-first: before writing, consider what concrete questions someone could
only answer by opening this group - about specific names, behaviors, values, rules,
or relationships in the content. Then write a summary that makes it obvious those
questions are answerable here:
- Start with what the group is as a whole.
- Organize by the natural groupings present in the content, naming the concrete
  identifiers and terms those questions would mention.
- End with a section "Answers questions like:" listing 5-8 of those questions,
  phrased the way a developer or agent would actually ask them.
- Mention only what is actually present in the content - do not invent anything.

Output only the summary in markdown, nothing else.""",

    # Level-2 composition test: do our level-1 summaries compose upward? The
    # "chunks" here are the existing adaptive-condensed__sonnet summaries of all
    # sample clusters, treated as children of one synthetic parent (cluster 100).
    "level2": """\
The chunks below are the summaries of the child nodes of one parent node in a
knowledge tree. Write the parent node's summary. An AI agent reads ONLY the parent
summary, next to summaries of other nodes at the same level, first to decide
whether to enter this subtree at all, and then which child to descend into.

Guidelines:
- State what the whole subtree covers: find the real common point of the children,
  do not just list them.
- Then characterize each child in one or two lines, by its chunk label, with the
  concrete names and terms that distinguish it from the other children - enough to
  pick the right child without opening it.
- Keep concrete identifiers from the child summaries verbatim; never invent or
  generalize names.
- If two children overlap, say explicitly how to choose between them.

Output only the summary in markdown, nothing else.""",
}

# ---- round 6: gotcha extraction (ACTIVE) --------------------------------
# Legacy systems hide non-obvious, bug-prone decisions. Move them UP into the
# abstraction so an agent is warned without reading the source.
PROMPTS["gotchas"] = """\
Examine the following group of related content chunks and report ONLY the
non-obvious things in it - whatever a newcomer would not expect and could be
hurt by:
- behavior that differs from what the names or structure suggest
- silent no-ops, swallowed errors, missing rollbacks, partial operations
  (e.g. multi-step writes that are not transactional)
- asymmetries and inconsistencies (two similar things handled differently)
- workarounds, hardcoded values, suspicious special cases
- anything surprising, illogical, or fragile

For each finding: one line stating the fact plus where it lives (file/name).
Only report what is literally in the content - do not speculate beyond it.
If there is genuinely nothing non-obvious, output exactly: "No gotchas found."
Output only the findings list."""

PROMPTS["adaptive-gotchas"] = PROMPTS["adaptive"].replace(
    "- Mention only what is actually present",
    """- End with a "Caution" section listing anything non-obvious a newcomer could
  be hurt by: behavior differing from what names suggest, silent no-ops, partial
  or non-transactional operations, asymmetries, workarounds, fragile special
  cases. Omit the section entirely if there is nothing to warn about.
- Mention only what is actually present""",
)

SIZE_BUDGET_TOKENS = 1500  # fills {size} in round-1 prompts when they run


def instructions(prompt_key: str) -> str:
    return PROMPTS[prompt_key].replace("{size}", str(SIZE_BUDGET_TOKENS))


def make_call(purpose: str, prompt: str, model: str) -> dict:
    result = call_claude(prompt, model)
    return {"purpose": purpose, "model": model, "prompt": prompt,
            "response": result["text"], "duration_ms": result["duration_ms"],
            "cost_usd": result["cost_usd"]}


def single_call(prompt_key: str, model: str, condensed: bool = False):
    """One-shot summary from raw chunks or from cached condensations."""
    def runner(cluster: "Cluster") -> list[dict]:
        content = (
            render_condensed(cluster.chunks, run_map_stage(cluster)) if condensed
            else render_chunks(cluster.chunks)
        )
        return [make_call("summary", instructions(prompt_key) + "\n\n" + content, model)]
    runner.condensed = condensed
    return runner


def refine_pipeline(model: str):
    """Draft with the adaptive prompt, then a second pass checks it against content."""
    def runner(cluster: "Cluster") -> list[dict]:
        content = render_chunks(cluster.chunks)
        draft = make_call("draft", instructions("adaptive") + "\n\n" + content, model)
        prompt = instructions("refine").replace("{draft}", draft["response"]) + "\n\n" + content
        return [draft, make_call("refine", prompt, model)]
    return runner


def outline_pipeline(model: str):
    """Split the task: first inventory the groupings, then write from the outline."""
    def runner(cluster: "Cluster") -> list[dict]:
        content = render_chunks(cluster.chunks)
        outline = make_call("outline", instructions("outline") + "\n\n" + content, model)
        prompt = instructions("outline-write").replace("{outline}", outline["response"]) + "\n\n" + content
        return [outline, make_call("write", prompt, model)]
    return runner


def contrast_call(model: str):
    """Sibling-aware summary: condensed input plus the siblings' existing summaries."""
    def runner(cluster: "Cluster") -> list[dict]:
        content = render_condensed(cluster.chunks, run_map_stage(cluster))
        siblings = render_siblings(load_sibling_summaries(cluster.id))
        prompt = (instructions("contrast") + "\n\n" + siblings
                  + "\n\nTHIS GROUP'S CONTENT:\n\n" + content)
        return [make_call("summary", prompt, model)]
    runner.condensed = True
    return runner


def load_sibling_summaries(cluster_id: str) -> list[tuple[str, str]]:
    """Existing best summaries (adaptive-condensed__sonnet) of every other cluster."""
    return [
        (path.parent.name.removeprefix("cluster-"), path.read_text())
        for path in sorted(EXPERIMENTS_DIR.glob("cluster-*/adaptive-condensed__sonnet.md"),
                           key=lambda p: int(p.parent.name.split("-")[1]))
        if path.parent.name.removeprefix("cluster-") != cluster_id
    ]


def render_siblings(siblings: list[tuple[str, str]]) -> str:
    return ("SIBLING NODE SUMMARIES (context only - not part of this group):\n\n"
            + "\n\n".join(f"=== sibling cluster {sid} ===\n{text}"
                          for sid, text in siblings))


# Active matrix. Existing outputs are skipped, so reruns only fill gaps.
# Past rounds, for the record:
#   round 1 (cluster 14): r1-naive/r1-structured/two-stage(=r1-structured over
#     condensed input) x sizes 500/1500, all on sonnet
#   round 2 (cluster 14): r2-freeform x (sonnet, haiku) x (raw, condensed)
#   round 3 (clusters 14/0/36): plain/adaptive/routing x haiku/sonnet, raw input
EXPERIMENTS = [
    (f"{prompt}__{model}", single_call(prompt, model))
    for prompt in ("plain", "adaptive", "routing")
    for model in ("haiku", "sonnet")
] + [
    ("adaptive-condensed__haiku", single_call("adaptive", "haiku", condensed=True)),
    ("adaptive-condensed__sonnet", single_call("adaptive", "sonnet", condensed=True)),
    ("refine__haiku", refine_pipeline("haiku")),
    ("outline__haiku", outline_pipeline("haiku")),
    ("json__haiku", single_call("json", "haiku")),
] + [
    # round 5: routing-oriented additions. REJECTED after review: contrast has a
    # circular dependency (sibling summaries need each other) and only exists at
    # regeneration time; the "Answers questions like:" section was disliked.
    # ("contrast-condensed__haiku", contrast_call("haiku")),
    # ("contrast-condensed__sonnet", contrast_call("sonnet")),
    # ("questions__haiku", single_call("questions", "haiku")),
    # round 6: surface the non-obvious (gotchas)
    ("gotchas__haiku", single_call("gotchas", "haiku")),
    ("adaptive-gotchas__haiku", single_call("adaptive-gotchas", "haiku")),
    # gotchas through the two-layer pipeline: map prompt captures per-file
    # GOTCHA lines, reduce aggregates them into the Caution section
    ("adaptive-gotchas-condensed__haiku", single_call("adaptive-gotchas", "haiku", condensed=True)),
]

# Level-2 composition test: a synthetic parent whose "chunks" are the existing
# best summaries (adaptive-condensed__sonnet) of all sample clusters. Selected by
# passing cluster id 100 on the command line; only these experiments run on it.
LEVEL2_CLUSTER_ID = "100"
LEVEL2_EXPERIMENTS = [
    ("level2__haiku", single_call("level2", "haiku")),
    ("level2__sonnet", single_call("level2", "sonnet")),
]


def main() -> None:
    cluster_ids = sys.argv[1:] or ["14"]
    for cluster_id in cluster_ids:
        if cluster_id == LEVEL2_CLUSTER_ID:
            cluster, experiments = load_level2_cluster(), LEVEL2_EXPERIMENTS
        else:
            cluster, experiments = load_cluster(cluster_id), EXPERIMENTS
        print(f"cluster {cluster.id}: {len(cluster.chunks)} chunks, "
              f"{sum(len(c.text) for c in cluster.chunks) // 1024}KB total")
        run_all_experiments(cluster, experiments)
    build_report()


def run_all_experiments(cluster: "Cluster", experiments=EXPERIMENTS) -> None:
    with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
        futures = {
            pool.submit(run_experiment, cluster, name, runner): name
            for name, runner in experiments
        }
        for future, name in futures.items():
            future.result()


def run_experiment(cluster: "Cluster", name: str, runner) -> None:
    """Run the experiment's call pipeline and save summary + every call made."""
    out_dir = EXPERIMENTS_DIR / f"cluster-{cluster.id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_file = out_dir / f"{name}.md"
    if summary_file.exists():
        print(f"  skipped (exists): {name}")
        return
    calls = runner(cluster)
    final = calls[-1]
    summary_file.write_text(final["response"])
    (out_dir / f"{name}.meta.json").write_text(json.dumps({
        "experiment": name,
        "model": final["model"],
        "condensed_input": getattr(runner, "condensed", False),
        "calls": calls,
        "prompt_chars": len(final["prompt"]),
        "prompt": final["prompt"],
        "response": final["response"],
        "duration_ms": sum(c["duration_ms"] or 0 for c in calls),
        "cost_usd": sum(c["cost_usd"] or 0 for c in calls),
    }, indent=2))
    print(f"  done: {name} ({len(calls)} calls)")


def render_condensed(chunks: list["Chunk"], mini_summaries: dict[str, str]) -> str:
    preamble = ("The chunks below were condensed by a smaller model; each section "
                "is a faithful distillation of one original chunk.\n\n")
    return preamble + "\n\n".join(
        f"=== {chunk.label} ===\n{mini_summaries[chunk.label]}" for chunk in chunks
    )


def render_chunks(chunks: list["Chunk"]) -> str:
    return "\n\n".join(f"=== {chunk.label} ===\n{chunk.text}" for chunk in chunks)


# --- Map stage (two-stage approach) -----------------------------------------

def run_map_stage(cluster: "Cluster") -> dict[str, str]:
    """Condense every chunk with the cheap model; cache results by content hash."""
    MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
        results = pool.map(condense_chunk, cluster.chunks)
    summaries = dict(zip((c.label for c in cluster.chunks), results))
    print(f"  map stage: {len(summaries)} mini-summaries ready")
    return summaries


def condense_chunk(chunk: "Chunk") -> str:
    cached = MAP_CACHE_DIR / f"{chunk.hash}.txt"
    if cached.exists():
        return cached.read_text()
    prompt = (
        "Condense this content chunk to its essential information. Let the length "
        "follow the density of the content: boilerplate, generated, or repetitive "
        "content collapses to one short line saying so; dense logic keeps whatever "
        "it needs to stay faithful. Copy concrete identifiers, names, values, and "
        "constraints VERBATIM from the content - never infer or add ones that are "
        "not literally there. If the content holds anything non-obvious a newcomer "
        "could be hurt by (behavior differing from what names suggest, silent "
        "no-ops, partial or non-transactional operations, asymmetries, workarounds, "
        "fragile special cases), add a line starting with 'GOTCHA:' for each - only "
        "if literally present. Output only the condensed content.\n\n"
        f"File: {chunk.label}\n\n{chunk.text}"
    )
    result = call_claude(prompt, MAP_MODEL)
    cached.write_text(result["text"])
    cached.with_suffix(".call.json").write_text(json.dumps({
        "chunk_label": chunk.label,
        "model": MAP_MODEL,
        "prompt": prompt,
        "response": result["text"],
        "duration_ms": result["duration_ms"],
        "cost_usd": result["cost_usd"],
    }, indent=2))
    return result["text"]


# --- Claude Code backend (Agent SDK) -----------------------------------------

def call_claude(prompt: str, model: str) -> dict:
    """One text-generation call via the Claude Agent SDK (subscription auth).

    Clean environment: no settings/skills/hooks, no tools, fresh temp cwd —
    so nothing from the user's Claude Code setup leaks into the summary.
    """
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(_call_claude(prompt, model, tmp))


async def _call_claude(prompt: str, model: str, cwd: str) -> dict:
    options = ClaudeAgentOptions(
        allowed_tools=[],
        setting_sources=[],
        plugins=[],
        permission_mode="default",
        model=model,
        cwd=cwd,
        include_partial_messages=False,
    )
    text_parts: list[str] = []
    result: ResultMessage | None = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            text_parts.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            result = msg
    if result is None:
        raise RuntimeError(f"claude SDK returned no ResultMessage ({model})")
    if result.is_error:
        raise RuntimeError(f"claude SDK error ({model}): {(result.result or '')[:500]}")
    return {
        "text": result.result if result.result is not None else "".join(text_parts),
        "duration_ms": result.duration_ms,
        "cost_usd": result.total_cost_usd,
    }


# --- Cluster loading ---------------------------------------------------------

@dataclass
class Chunk:
    label: str  # filename-derived: <NNN>__<path>__chunk-<n>
    hash: str
    text: str


@dataclass
class Cluster:
    id: str
    chunks: list[Chunk]
    members: list[dict]


def load_cluster(cluster_id: str) -> Cluster:
    """Read one sample cluster extracted by build_clusters.py."""
    cluster_dir = SAMPLES_DIR / f"cluster-{cluster_id}"
    meta = json.loads((cluster_dir / "meta.json").read_text())
    chunks = []
    for path in sorted((cluster_dir / "chunks").iterdir()):
        chunks.append(Chunk(
            label=path.stem,
            hash=find_hash_for(path.stem, meta["members"]),
            text=path.read_text(errors="replace"),
        ))
    return Cluster(id=cluster_id, chunks=chunks, members=meta["members"])


def find_hash_for(label: str, members: list[dict]) -> str:
    """Match a chunk file back to its member record via the chunk ordinal prefix."""
    ordinal = int(label.split("__")[0])
    return members[ordinal]["hash"]


def load_level2_cluster() -> Cluster:
    """Synthetic level-2 cluster: the existing best summary of every level-1 cluster."""
    chunks = []
    for path in sorted(EXPERIMENTS_DIR.glob("cluster-*/adaptive-condensed__sonnet.md"),
                       key=lambda p: int(p.parent.name.split("-")[1])):
        text = path.read_text()
        chunks.append(Chunk(
            label=f"summary-of-cluster-{path.parent.name.removeprefix('cluster-')}",
            hash=hashlib.sha256(text.encode()).hexdigest(),
            text=text,
        ))
    return Cluster(id=LEVEL2_CLUSTER_ID, chunks=chunks, members=[])


if __name__ == "__main__":
    main()
