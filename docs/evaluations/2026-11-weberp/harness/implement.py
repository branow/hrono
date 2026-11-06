"""One implementation run: a fresh workspace at a base commit, one headless Claude Code agent.

Usage: implement.py TASK BASE ARM TRY   (ARM is code or hrono)
Version 2 (amendment 2): the hrono arm runs the real hrono plugin
(--plugin-dir), so its SessionStart note, its skill and its recall hook
(UserPromptSubmit: `hrono recall` on the prompt, attached as context) work as
in a normal session. Version 1 pasted the note and skill into the prompt under
--safe-mode, which turned every hook off, so recall never ran.

Both arms: no --safe-mode; --setting-sources "" and --strict-mcp-config, so
no user or project settings, CLAUDE.md, plugins or MCP servers load, except
Claude Code's built-ins. The workspace is webERP at BASE as plain files plus
task/task.md, committed once; the agent's work is `git diff` afterwards. The
prompt is passed as an argument (the recall hook reads it). The hrono arm
also gets the export (--add-dir) and an entry in home/agent.json (the
plugin's settings) for its workspace; its recall answers from the live tree,
so the run refuses to start unless the source mirror's pin is BASE. The
recall text the hook attaches is saved as <run>.recall.md.
"""
import fcntl, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path.home() / "hrono-weberp"
EVAL = Path("/Users/orest/repos/hrono/docs/evaluations/2026-11-weberp")
PLUGIN = Path("/Users/orest/repos/hrono/plugins/hrono")
MODEL = os.environ.get("MODEL", "sonnet")
TURNS = int(os.environ.get("TURNS", "200"))
TOOLS = "Read,Grep,Glob,Edit,Write,TodoWrite,Skill"
HOME = ROOT / "home"  # HRONO_HOME: the plugin settings (agent.json) and the CLI profile
BIN = ROOT / "hr"  # hrono CLI on the venv binary (uv run is slower than the hook timeout)
# THREADS=<dir>: the repository's GitHub threads (issues, pull requests,
# discussions) as markdown, copied into both arms' workspaces as github/.
THREADS = os.environ.get("THREADS")
# EXPORT=<folder under exports/>: the map the hrono arm reads (default: the base's).
EXPORT = os.environ.get("EXPORT")
TREE = "weberp"
# READ_MAP=1 (amendment 5): the hrono arm's prompt also asks it to read the map's
# area and topic briefs for the request, project history included, before any edit.
READ_MAP = os.environ.get("READ_MAP") == "1"
READ_MAP_TEXT = (
    "\n\nBefore you change any file, read the project's map in {export}: root.md, the"
    " brief of every area the request touches, and every topic brief under those areas"
    " whose title touches the request, including the project-history briefs (issues,"
    " pull requests, discussions) on the same subjects. Read each in full. Where a"
    " brief states a convention or a decision that differs from what older code does,"
    " follow the brief. Then do the task.")


def configure(ws: Path, export: Path) -> None:
    """Name the tree and export for this workspace in the plugin's settings."""
    path = HOME / "agent.json"
    with open(HOME / "agent.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else {"projects": {}}
        data["projects"][str(ws.resolve())] = {"tree": TREE, "folder": str(export), "bin": str(BIN)}
        path.write_text(json.dumps(data, indent=1))


def recalled(ws: Path, prompt: str) -> str:
    """What the plugin's recall hook attaches to ``prompt`` (same code, same tree)."""
    event = {"hook_event_name": "UserPromptSubmit", "cwd": str(ws.resolve()), "prompt": prompt,
             "session_id": "harness"}
    run = subprocess.run(["node", str(PLUGIN / "scripts" / "hooks" / "recall.js")], input=json.dumps(event),
                         capture_output=True, text=True, env={**os.environ, "HRONO_HOME": str(HOME)})
    try:
        return json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        return f"(no recall: exit {run.returncode}) {run.stdout}{run.stderr}"


def workspace(task: str, base: str, arm: str, attempt: str) -> Path:
    ws = ROOT / "runs" / f"{task}-{arm}-{attempt}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    tar = subprocess.run(["git", "-C", str(ROOT / "upstream.git"), "archive", base],
                         capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(ws)], input=tar, check=True)
    if THREADS:
        shutil.copytree(THREADS, ws / "github")
    (ws / "task").mkdir()
    for src in sorted((EVAL / "tasks" / task).iterdir()):  # task.md and its inputs (brd.md), never the answers
        if src.name not in ("checklist.md", "reference.diff"):
            shutil.copy(src, ws / "task" / src.name)
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
    if THREADS:
        prompt += (" The repository's GitHub issues, pull requests and discussions up to"
                   " the base date are in github/, one markdown file per thread.")
    if os.environ.get("BUDGET_NOTE") == "1":  # amendment 7: both arms are told the turn budget
        prompt += (f" You have a budget of {TURNS} turns for the whole task; plan your reading so"
                   " that the change is complete and NOTES.md written within it.")
    argv = ["claude", "-p", prompt, "--model", MODEL, "--max-turns", str(TURNS),
            "--setting-sources", "", "--strict-mcp-config",
            "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
            "--disallowedTools", "Bash,WebFetch,WebSearch,Task,NotebookEdit",
            "--allowedTools", TOOLS]
    out = ROOT / "runs"
    env = dict(os.environ)
    if arm == "hrono":
        pin = subprocess.run(["git", "-C", str(ROOT / "mirror" / "webERP.git"), "rev-parse", "master"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if pin != base:
            sys.exit(f"the live tree is at {pin}, not {base}: recall would answer from the wrong commit")
        export = ROOT / "exports" / (EXPORT or base)
        configure(ws, export)
        if READ_MAP:
            prompt += READ_MAP_TEXT.format(export=export)
            argv[2] = prompt
        argv += ["--plugin-dir", str(PLUGIN), "--add-dir", str(export)]
        env["HRONO_HOME"] = str(HOME)
        (out / f"{ws.name}.recall.md").write_text(recalled(ws, prompt))
    (out / f"{ws.name}.prompt.md").write_text(prompt)
    (out / f"{ws.name}.argv.json").write_text(json.dumps(argv, indent=1))
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    proc = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=ws, env=env,
                          timeout=4 * 3600)
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
