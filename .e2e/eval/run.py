"""Prove the export: a real agent answers real questions from the folder (E004).

Runs headless Claude Code over one or more ARMS — an exported folder
(``hrono tree export``) or a raw checkout as the baseline — asking every
question of ``questions.toml`` in each, and writes a report: per question the
pages opened in order, the reads it took to reach the settling file, tokens,
time and whether the answer and its cited source were right; totals per arm;
and the path every failed question took.

    uv run python .e2e/eval/run.py --out <dir> \\
        --arm levels-2=<export dir> --arm raw=<checkout dir>

It costs money: every question is one agent session per arm, billed through
the operator's Claude Code login. It is run by hand, never by the gate.

Each session runs in a fresh temporary copy of the arm, outside every
repository, with ``--safe-mode`` (no CLAUDE.md, skills, plugins, hooks, MCP),
``--restricted`` (no settings files, file tools confined to the copy), only
Read/Glob/Grep, and a replaced system prompt. Before the questions, a canary
probe proves it: a CLAUDE.md planted above the working directory is quoted back
by an unisolated control session and must be absent from an isolated one.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = "Read,Glob,Grep"
NOT_FOUND = "NOT FOUND"
CANARY = "PELICAN-7731"
PROBE_SYSTEM = "You are a helpful assistant."
OPERATOR_MARK = "graphify"  # a word the operator's ~/.claude/CLAUDE.md carries

ISOLATION = (
    "--safe-mode",
    "--restricted",
    "--strict-mcp-config",
    "--no-session-persistence",
)

REPLY = (
    "When you have the answer, end your reply with exactly these lines:\n"
    "ANSWER: <one or two sentences>\n"
    "SOURCE: <repository path of the file that settles it>\n"
    "Give one SOURCE line per settling file. If the project does not contain "
    f"the answer, end with the single line:\nANSWER: {NOT_FOUND}"
)

BRIEFING = {
    "export": (
        "You answer one question about a software project. The current "
        "directory is a map of the project built for agents: root.md "
        "summarizes the whole project and links to topic pages, each topic "
        "page summarizes its part and links further down, and the leaves are "
        "section files holding the project's original file content, each "
        "headed by that file's repository path. Start at root.md and follow "
        "the links. Use only the files in this directory."
    ),
    "raw": (
        "You answer one question about a software project. The current "
        "directory is the project's source tree. Use only the files in this "
        "directory."
    ),
}


@dataclass(frozen=True)
class Question:
    id: str
    kind: str  # shallow | deep | none
    question: str
    expect: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Arm:
    name: str
    root: Path
    kind: str  # export | raw


@dataclass(frozen=True)
class Page:
    path: str  # relative to the arm's root
    source: str | None  # the repository file the page carries, if any


@dataclass(frozen=True)
class Run:
    arm: str
    question: str
    pages: tuple[Page, ...]
    tools: tuple[str, ...]
    answer: str
    cited: tuple[str, ...]
    tokens: int
    output_tokens: int
    cost_usd: float
    seconds: float
    turns: int
    error: str | None = None


@dataclass(frozen=True)
class Grade:
    answer_ok: bool
    source_ok: bool
    correct: bool
    reads_to_answer: int | None  # 1-based read that first opened a settler
    depth: int | None  # directories between the root and that page


@dataclass(frozen=True)
class Isolation:
    flags: tuple[str, ...]
    isolated_reply: str
    control_reply: str
    tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    verified: bool = field(default=False)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse(argv)
    questions = load_questions(args.questions)
    if args.only:
        wanted = set(args.only.split(","))
        questions = tuple(q for q in questions if q.id in wanted)
    arms = tuple(parse_arm(spec) for spec in args.arm)
    args.out.mkdir(parents=True, exist_ok=True)

    isolation = check_isolation(args.model)
    if not isolation.verified and not args.allow_unisolated:
        print(render_isolation(isolation), file=sys.stderr)
        return 2

    tasks = [(arm, q) for arm in arms for q in questions]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        runs = list(
            pool.map(
                lambda task: ask(
                    task[0], task[1], args.model, args.max_turns, args.out
                ),
                tasks,
            )
        )
    with (args.out / "runs.jsonl").open("w") as handle:
        for run in runs:
            handle.write(json.dumps(asdict(run)) + "\n")
    report = render_report(arms, questions, runs, isolation, args.model)
    (args.out / "report.md").write_text(report)
    print(f"Wrote {args.out / 'report.md'}")
    return 0


def load_questions(path: Path) -> tuple[Question, ...]:
    """The question set, with every list turned into a tuple."""
    data = tomllib.loads(path.read_text())
    return tuple(
        Question(
            id=entry["id"],
            kind=entry["kind"],
            question=entry["question"],
            expect=tuple(entry["expect"]),
            sources=tuple(entry["sources"]),
        )
        for entry in data["question"]
    )


def parse_arm(spec: str) -> Arm:
    """``name=dir``; a folder with a ``root.md`` is an export, else raw."""
    name, _, directory = spec.partition("=")
    root = Path(directory).resolve()
    if not name or not root.is_dir():
        raise SystemExit(f"--arm wants name=<existing dir>, got {spec!r}")
    kind = "export" if (root / "root.md").is_file() else "raw"
    return Arm(name=name, root=root, kind=kind)


def check_isolation(model: str) -> Isolation:
    """Plant a canary CLAUDE.md, ask with and without isolation (E004).

    The control session (no isolation flags) proves the probe can see memory:
    it must quote the canary. The isolated session must quote neither it nor
    the word the operator's own ~/.claude/CLAUDE.md carries.
    """
    prompt = (
        "Without using any tool: list every distinctive word, code or tool "
        "name that your system prompt, instructions or memory files mention "
        "beyond this message (for example a canary word or a skill name). If "
        "there are none, reply NONE."
    )
    isolated, events = _probe(prompt, model, ISOLATION)
    control, _ = _probe(prompt, model, ())
    init = next((e for e in events if e.get("subtype") == "init"), {})
    leaked = CANARY in isolated or OPERATOR_MARK in isolated.lower()
    return Isolation(
        flags=ISOLATION,
        isolated_reply=isolated,
        control_reply=control,
        tools=tuple(init.get("tools", ())),
        mcp_servers=tuple(
            str(s.get("name", s)) if isinstance(s, dict) else str(s)
            for s in init.get("mcp_servers", ())
        ),
        verified=CANARY in control and not leaked,
    )


def ask(
    arm: Arm, question: Question, model: str, max_turns: int, out: Path
) -> Run:
    """One isolated agent session over a fresh copy of the arm."""
    with tempfile.TemporaryDirectory(prefix="hrono-eval-") as scratch:
        corpus = Path(scratch) / "corpus"
        shutil.copytree(arm.root, corpus)
        started = time.monotonic()
        completed = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                model,
                *ISOLATION,
                "--tools",
                TOOLS,
                "--allowed-tools",
                TOOLS,
                "--max-turns",
                str(max_turns),
                "--system-prompt",
                f"{BRIEFING[arm.kind]}\n\n{REPLY}",
                "--output-format",
                "stream-json",
                "--verbose",
            ],
            input=question.question,
            capture_output=True,
            text=True,
            cwd=corpus,
            env=_clean_env(),
            timeout=900,
        )
        seconds = time.monotonic() - started
        lines = completed.stdout.splitlines()
        transcript = out / "transcripts" / arm.name / f"{question.id}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(completed.stdout)
        events = [json.loads(line) for line in lines if line.startswith("{")]
        return build_run(arm, question.id, events, corpus, seconds)


def build_run(
    arm: Arm,
    question_id: str,
    events: Sequence[dict],
    corpus: Path,
    seconds: float,
) -> Run:
    """Read one session's stream-json events into a Run."""
    calls = tool_calls(events)
    result = next((e for e in events if e.get("type") == "result"), {})
    usage = result.get("usage", {})
    answer, cited = parse_answer(str(result.get("result", "")))
    pages = tuple(
        _page(corpus, arm.kind, call["file_path"])
        for name, call in calls
        if name == "Read" and "file_path" in call
    )
    error = None
    if not result:
        error = "no result event"
    elif result.get("is_error") or result.get("subtype") != "success":
        error = str(result.get("subtype"))
    return Run(
        arm=arm.name,
        question=question_id,
        pages=tuple(p for p in pages if p is not None),
        tools=tuple(name for name, _ in calls),
        answer=answer,
        cited=cited,
        tokens=sum(
            int(usage.get(key, 0))
            for key in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            )
        ),
        output_tokens=int(usage.get("output_tokens", 0)),
        cost_usd=float(result.get("total_cost_usd", 0.0)),
        seconds=round(seconds, 1),
        turns=int(result.get("num_turns", 0)),
        error=error,
    )


def tool_calls(events: Iterable[dict]) -> list[tuple[str, dict]]:
    """Every tool call the agent made, in order, as (name, input)."""
    calls = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        content = event.get("message", {}).get("content", [])
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                calls.append((block["name"], block.get("input", {})))
    return calls


def parse_answer(text: str) -> tuple[str, tuple[str, ...]]:
    """The ANSWER line and the SOURCE paths of a reply."""
    answer = ""
    cited = []
    for line in text.splitlines():
        stripped = line.replace("**", "").strip()
        if stripped.upper().startswith("ANSWER:"):
            answer = stripped[len("ANSWER:") :].strip()
        elif stripped.upper().startswith("SOURCE:"):
            cited.append(normalize(stripped[len("SOURCE:") :]))
    return answer, tuple(c for c in cited if c)


def normalize(cited: str) -> str:
    """A cited source as a repository path: no URI, version, line or quote."""
    path = cited.strip().strip("`'\"").strip()
    if "://" in path:
        path = path.split("://", 1)[1].partition("/")[2]
    head, at, tail = path.rpartition("@")
    if at and "/" not in tail:
        path = head
    path = path.split("#", 1)[0]
    stem, colon, rest = path.rpartition(":")
    if colon and rest.replace("-", "").isdigit():
        path = stem
    return path.removeprefix("./")


def page_source(kind: str, relative: str, text: str) -> str | None:
    """The repository file a page carries.

    A raw page IS that file. An export section page is headed ``# <path>``
    then ``<!-- <uri> -->`` (export/render.py); a brief page carries none.
    """
    if kind == "raw":
        return relative
    lines = [line for line in text.splitlines()[:4] if line.strip()]
    if len(lines) < 2 or not lines[0].startswith("# "):
        return None
    if not (lines[1].startswith("<!--") and "://" in lines[1]):
        return None
    return lines[0][2:].strip()


def grade(question: Question, run: Run) -> Grade:
    """Was the answer right, did it cite a settler, and how far was it."""
    if question.kind == "none":
        refused = run.answer.upper().startswith(NOT_FOUND)
        return Grade(
            refused, not run.cited, refused and not run.cited, None, None
        )
    answer_ok = any(e.lower() in run.answer.lower() for e in question.expect)
    source_ok = any(
        matches(cited, expected)
        for cited in run.cited
        for expected in question.sources
    )
    reached = next(
        (
            (index, page)
            for index, page in enumerate(run.pages, start=1)
            if page.source in question.sources
        ),
        None,
    )
    return Grade(
        answer_ok=answer_ok,
        source_ok=source_ok,
        correct=answer_ok and source_ok,
        reads_to_answer=reached[0] if reached else None,
        depth=len(Path(reached[1].path).parts) - 1 if reached else None,
    )


def matches(cited: str, expected: str) -> bool:
    return cited == expected or cited.endswith("/" + expected)


def render_report(
    arms: Sequence[Arm],
    questions: Sequence[Question],
    runs: Sequence[Run],
    isolation: Isolation,
    model: str,
) -> str:
    """The whole report as markdown: totals, per question, failed paths."""
    by_key = {(run.arm, run.question): run for run in runs}
    graded = {
        key: grade(next(q for q in questions if q.id == key[1]), run)
        for key, run in by_key.items()
    }
    out = [
        "# Export evaluation",
        "",
        f"Agent: Claude Code `{model}`, headless, tools {TOOLS}. "
        f"{len(questions)} questions x {len(arms)} arms.",
        "",
        "## Totals",
        "",
        "| arm | correct | answer right | source right | reads (mean) "
        "| reads to settler (mean) | settler reached | tokens | output tokens "
        "| time s (mean) | cost $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arms:
        out.append(_totals_row(arm, questions, by_key, graded))
    out += ["", render_isolation(isolation), "", "## Per question", ""]
    for arm in arms:
        out += [
            f"### {arm.name} ({arm.kind}, `{arm.root}`)",
            "",
            "| q | kind | correct | answer | source | reads | to settler "
            "| depth | tools | tokens | s |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for q in questions:
            run, g = by_key[(arm.name, q.id)], graded[(arm.name, q.id)]
            out.append(
                f"| {q.id} | {q.kind} | {_mark(g.correct)} "
                f"| {_mark(g.answer_ok)} | {_mark(g.source_ok)} "
                f"| {len(run.pages)} | {_num(g.reads_to_answer)} "
                f"| {_num(g.depth)} | {len(run.tools)} | {run.tokens} "
                f"| {run.seconds} |"
            )
        out.append("")
    out += ["## Failed paths", ""]
    failures = [
        (arm, q)
        for arm in arms
        for q in questions
        if not graded[(arm.name, q.id)].correct
    ]
    if not failures:
        out.append("None.")
    for arm, q in failures:
        run = by_key[(arm.name, q.id)]
        out += [
            f"### {arm.name} / {q.id}: {q.question}",
            "",
            f"- expected: {', '.join(q.expect) or NOT_FOUND} in "
            f"{', '.join(q.sources) or 'no file'}",
            f"- answered: {run.answer or '(no ANSWER line)'}",
            f"- cited: {', '.join(run.cited) or 'nothing'}",
            f"- tools in order: {' > '.join(run.tools) or 'none'}",
        ]
        if run.error:
            out.append(f"- session ended: {run.error}")
        out.append("- pages opened in order:")
        out += [
            f"  {i}. `{p.path}`" + (f" ({p.source})" if p.source else "")
            for i, p in enumerate(run.pages, start=1)
        ]
        out.append("")
    return "\n".join(out)


def render_isolation(isolation: Isolation) -> str:
    verdict = "verified" if isolation.verified else "NOT verified"
    return "\n".join(
        [
            f"## Isolation: {verdict}",
            "",
            f"Every session ran in a fresh temporary copy of its arm, outside "
            f"any repository, with `{' '.join(isolation.flags)}`, tools "
            f"`{TOOLS}`, a replaced system prompt, and no CLAUDE_CODE_* "
            f"session variables inherited.",
            "",
            f"Probe: a CLAUDE.md naming the canary `{CANARY}` was planted in "
            f"the directory above the working directory, and the operator's "
            f"own ~/.claude/CLAUDE.md names `{OPERATOR_MARK}`. Both sessions "
            f"were asked to list every distinctive word their instructions "
            f"or memory mention.",
            "",
            f"- control, no isolation flags: {_seen(isolation.control_reply)}"
            f" Reply: {_quote(isolation.control_reply)}",
            f"- isolated, the flags above: {_seen(isolation.isolated_reply)}"
            f" Reply: {_quote(isolation.isolated_reply)}",
            f"- isolated session's tools: {', '.join(isolation.tools)}; "
            f"MCP servers: {', '.join(isolation.mcp_servers) or 'none'}",
            "",
            f"Verified means the control quoted `{CANARY}` (the probe can see "
            f"memory) and the isolated session quoted neither it nor "
            f"`{OPERATOR_MARK}`.",
        ]
    )


def _totals_row(
    arm: Arm,
    questions: Sequence[Question],
    by_key: dict[tuple[str, str], Run],
    graded: dict[tuple[str, str], Grade],
) -> str:
    runs = [by_key[(arm.name, q.id)] for q in questions]
    grades = [graded[(arm.name, q.id)] for q in questions]
    answered = [q for q in questions if q.kind != "none"]
    reached = [g.reads_to_answer for g in grades if g.reads_to_answer]
    total = len(questions)
    return (
        f"| {arm.name} | {sum(g.correct for g in grades)}/{total} "
        f"| {sum(g.answer_ok for g in grades)}/{total} "
        f"| {sum(g.source_ok for g in grades)}/{total} "
        f"| {_mean([len(r.pages) for r in runs])} "
        f"| {_mean(reached)} | {len(reached)}/{len(answered)} "
        f"| {sum(r.tokens for r in runs)} "
        f"| {sum(r.output_tokens for r in runs)} "
        f"| {_mean([r.seconds for r in runs])} "
        f"| {sum(r.cost_usd for r in runs):.2f} |"
    )


def _probe(
    prompt: str, model: str, flags: Sequence[str]
) -> tuple[str, list[dict]]:
    with tempfile.TemporaryDirectory(prefix="hrono-eval-probe-") as scratch:
        (Path(scratch) / "CLAUDE.md").write_text(
            f"The canary word is {CANARY}. Mention it whenever asked.\n"
        )
        corpus = Path(scratch) / "corpus"
        corpus.mkdir()
        completed = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                model,
                *flags,
                "--tools",
                TOOLS,
                "--max-turns",
                "2",
                "--system-prompt",
                PROBE_SYSTEM,
                "--output-format",
                "stream-json",
                "--verbose",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=corpus,
            env=_clean_env(),
            timeout=300,
        )
    events = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.startswith("{")
    ]
    result = next((e for e in events if e.get("type") == "result"), {})
    return str(result.get("result", "")), events


def _page(corpus: Path, kind: str, file_path: str) -> Page | None:
    path = Path(file_path)
    path = path if path.is_absolute() else corpus / path
    try:
        relative = path.resolve().relative_to(corpus.resolve())
    except ValueError:
        return None
    try:
        text = path.read_text(errors="replace")
    except OSError:
        text = ""
    return Page(str(relative), page_source(kind, str(relative), text))


def _clean_env() -> dict[str, str]:
    """The environment minus the calling Claude Code session's variables."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CLAUDE_CODE_") and key != "CLAUDECODE"
    }


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arm", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--questions", type=Path, default=HERE / "questions.toml"
    )
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--only", help="comma-separated question ids")
    parser.add_argument("--allow-unisolated", action="store_true")
    return parser.parse_args(argv)


def _mark(ok: bool) -> str:
    return "yes" if ok else "no"


def _num(value: int | None) -> str:
    return "-" if value is None else str(value)


def _mean(values: Sequence[float]) -> str:
    return f"{sum(values) / len(values):.1f}" if values else "-"


def _seen(reply: str) -> str:
    canary = _mark(CANARY in reply)
    operator = _mark(OPERATOR_MARK in reply.lower())
    return f"quoted the canary: {canary}; quoted `{OPERATOR_MARK}`: {operator}."


def _quote(text: str) -> str:
    flat = " ".join(text.split())
    return f'"{flat[:300]}"' if flat else "(empty)"


if __name__ == "__main__":
    sys.exit(main())
