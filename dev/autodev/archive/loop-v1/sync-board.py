"""Bring board.md's rows for #201+ in line with the stage folders (PO only)."""

import re
from pathlib import Path

BOARD = Path(__file__).parent.parent / "board"
STAGES = ("backlog", "todo", "in-progress", "verifying", "po-review", "done")


def tickets() -> dict[int, tuple[str, dict[str, str]]]:
    found = {}
    for stage in STAGES:
        for path in (BOARD / stage).glob("*.md"):
            head = path.read_text().split("---")[1]
            meta = dict(re.findall(r"^(\w+): (.*)$", head, re.M))
            found[int(meta["id"])] = (stage, meta)
    return found


def row(ticket: int, stage: str, meta: dict[str, str]) -> str:
    deps = meta.get("depends_on", "[]").strip("[]") or "-"
    return (
        f"| {ticket} | {meta['title']} | {stage} | "
        f"{meta['priority']} | {meta['size']} | {deps} |"
    )


def main() -> None:
    index = BOARD / "board.md"
    lines = index.read_text().split("\n")
    current = {t: v for t, v in tickets().items() if t >= 201}
    seen = set()
    last = 0
    for i, line in enumerate(lines):
        match = re.match(r"\| (\d+) \|", line)
        if not match:
            continue
        last = i
        ticket = int(match.group(1))
        if ticket in current:
            lines[i] = row(ticket, *current[ticket])
            seen.add(ticket)
    extra = [row(t, *current[t]) for t in sorted(current) if t not in seen]
    lines[last + 1 : last + 1] = extra
    index.write_text("\n".join(lines))
    for stage in STAGES[1:]:
        ids = sorted(t for t, (s, _) in current.items() if s == stage)
        print(f"{stage}: {ids}")


main()
