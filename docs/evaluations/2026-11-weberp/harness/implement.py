"""One implementation run: a fresh workspace at a base commit, one headless Claude Code agent.

Usage: implement.py TASK BASE ARM TRY   (ARM is code or hrono)
Adapted from the PDP harness (same model, turns, tools, flags and hrono
note). The workspace is webERP at BASE as plain files (no history) plus
task/task.md; it is committed once, so the agent's work is `git diff`
afterwards. Both arms: same model, turns, tools, prompt; the hrono arm adds
the tree export (read-only, via --add-dir) and the hrono plugin's own
session note and skill.
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path.home() / "hrono-weberp"
EVAL = Path("/Users/orest/repos/hrono/docs/evaluations/2026-11-weberp")
PLUGIN = Path("/Users/orest/repos/hrono/plugins/hrono")
MODEL = os.environ.get("MODEL", "sonnet")
TURNS = int(os.environ.get("TURNS", "200"))
TOOLS = "Read,Grep,Glob,Edit,Write,TodoWrite"
TREE = "weberp"


def plugin_note(export: Path, tree: str) -> str:
    """What the hrono plugin says at session start, plus its skill."""
    js = (PLUGIN / "scripts" / "hooks" / "session-start.js").read_text()
    part = js[js.index("It is exported at") - 2: js.index("lines.push(`It is not")]
    note = "".join(p[1:-1] for p in re.findall(r'(`[^`]*`|"[^"]*")', part))
    note = note.replace("${config.folder}", str(export)).replace(" (${when})", "")
    note = note.replace("${root}", str(export / "root.md"))
    skill = (PLUGIN / "skills" / "hrono" / "SKILL.md").read_text().split("---", 2)[2]
    head = (f'This project has an hrono map (tree "{tree}"): briefs of everything '
            "its sources hold, from one overview down to the files. ")
    return "\n\n" + head + note + "\n\nThe hrono skill:\n" + skill.strip()


def workspace(task: str, base: str, arm: str, attempt: str) -> Path:
    ws = ROOT / "runs" / f"{task}-{arm}-{attempt}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    tar = subprocess.run(["git", "-C", str(ROOT / "upstream.git"), "archive", base],
                         capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(ws)], input=tar, check=True)
    (ws / "task").mkdir()
    shutil.copy(EVAL / "tasks" / task / "task.md", ws / "task" / "task.md")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=eval", "-c", "user.email=eval@local",
                                                 "commit", "-q", "-m", "baseline"]):
        subprocess.run(["git", "-C", str(ws), *args], check=True)
    return ws


def main() -> None:
    task, base, arm, attempt = sys.argv[1:5]
    ws = workspace(task, base, arm, attempt)
    prompt = (ws / "task" / "task.md").read_text()
    prompt += "\n\nThe webERP repository is in the current directory; the task is task/task.md."
    prompt += " There is nothing to run against: deliver the change as files."
    argv = ["claude", "-p", "--model", MODEL, "--max-turns", str(TURNS), "--safe-mode",
            "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
            "--disallowedTools", "Bash,WebFetch,WebSearch,Task,NotebookEdit",
            "--allowedTools", TOOLS]
    if arm == "hrono":
        export = ROOT / "exports" / base
        prompt += plugin_note(export, TREE)
        argv += ["--add-dir", str(export)]
    out = ROOT / "runs"
    (out / f"{ws.name}.prompt.md").write_text(prompt)
    (out / f"{ws.name}.argv.json").write_text(json.dumps(argv, indent=1))
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    proc = subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=ws, timeout=4 * 3600)
    (out / f"{ws.name}.jsonl").write_text(proc.stdout)
    (out / f"{ws.name}.stderr").write_text(proc.stderr)
    result, models = {}, set()
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            result = ev
        if ev.get("type") == "assistant":
            models.add(ev.get("message", {}).get("model"))
    subprocess.run(["git", "-C", str(ws), "add", "-A"], check=True)
    stat = subprocess.run(["git", "-C", str(ws), "diff", "--cached", "--stat"], capture_output=True, text=True).stdout
    with open(out / f"{ws.name}.diff", "w") as fh:
        subprocess.run(["git", "-C", str(ws), "diff", "--cached"], stdout=fh, check=True)
    summary = {"task": task, "base": base, "arm": arm, "try": attempt, "model_alias": MODEL,
               "models_reported": sorted(m for m in models if m), "started_utc": started,
               "seconds": round(time.time() - t0), "turns": result.get("num_turns"),
               "max_turns": TURNS, "subtype": result.get("subtype"), "is_error": result.get("is_error"),
               "cost_usd": result.get("total_cost_usd"), "usage": result.get("usage"),
               "exit_code": proc.returncode,
               "stat": stat.strip().splitlines()[-1:] if stat else [], "stderr_tail": proc.stderr[-500:]}
    (out / f"{ws.name}.summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
