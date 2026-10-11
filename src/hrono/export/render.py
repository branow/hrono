"""Render the collapsed agent-facing tree to a path -> markdown mapping.

The export is the KNOWLEDGE, not the information: briefs only. The agent that
reads it already has the repositories, so a leaf ends with pointers to its
source files and copies none of them.

Per agent node: its stored brief text as-is (already ends with its Caution
section; never regenerated), then a MECHANICAL child listing rendered from the
collapsed tree in code (titles + relative links, no LLM, no hallucinated
links; each entry below the root also names a few source files beneath it). A
leaf lists its source files instead. Human notes render only when passed. No
file I/O — returns a deterministic path -> content map that the caller
materialises into a folder tree.

Every key is RELATIVE and unique. The root's own brief is ``root.md``; every
other node owns an id-suffixed directory, so no path can start with "/" (which
pathlib would let reroot the whole export out of the output folder) and no two
briefs can land on one key.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping

from hrono.export.collapse import ExportTree
from hrono.naming import heading, names, sentence, slug, unframe
from hrono.summarize import briefs


def render(
    conn: sqlite3.Connection,
    tree: ExportTree,
    *,
    notes: Mapping[int, str] | None = None,
) -> dict[str, str]:
    """Render ``tree`` to a {file path -> markdown content} mapping."""
    notes = notes or {}
    parent = {
        child: node.node_id
        for node in tree.nodes.values()
        for child in node.children
    }
    files: dict[str, str] = {}
    stems = _stems(conn, tree)
    for node_id in sorted(tree.nodes):
        node = tree.nodes[node_id]
        directory = _directory(node_id, parent, tree.root, stems)
        path = "root.md" if node_id == tree.root else _under(directory, "brief")
        text = _brief_text(conn, node_id)
        if node.children:
            text = _routing(text)
        files[path] = _node_markdown(
            conn,
            tree,
            node_id,
            notes.get(node_id),
            text,
            stems,
        )
    return files


def _under(directory: str, name: str) -> str:
    """Join a name under a directory, staying RELATIVE for the root ("")."""
    return f"{directory}/{name}.md" if directory else f"{name}.md"


def _node_markdown(
    conn: sqlite3.Connection,
    tree: ExportTree,
    node_id: int,
    note: str | None,
    brief: str,
    stems: Mapping[int, str],
) -> str:
    node = tree.nodes[node_id]
    parts = [brief.rstrip()]
    if node.children:
        called = names(conn, node.children)
        parts.append("## Children")
        parts.append(
            "\n".join(
                _child_entry(conn, child, called[child], stems)
                for child in node.children
            )
        )
    elif node.sections:
        parts.append("## Sources")
        parts.append(_sources(conn, node.sections))
    if note:
        parts.append(f"## Notes\n\n{note}")
    return "\n\n".join(parts) + "\n"


def _routing(brief: str) -> str:
    """An index page's opening, which says what its subtree is about.

    The root is read first and the pages under it next, and every later turn
    carries them, so their length is paid for on each turn (a 24 KB root makes
    the export cost more than the raw repository). What an index page owes
    the reader is where to go, and ``## Children`` says that; the facts under a
    brief's own headings live in the children and their sections, so the page
    keeps only what comes before the first heading that follows prose.
    """
    kept: list[str] = []
    prose = False
    for line in brief.splitlines():
        if line.startswith("## ") and prose:
            break
        prose = prose or bool(line.strip() and not line.startswith("#"))
        kept.append(line)
    return "\n".join(kept)


def _child_entry(
    conn: sqlite3.Connection,
    child: int,
    title: str,
    stems: Mapping[int, str],
) -> str:
    """An index page's entry: title, link and what the child holds.

    The summary is there so an agent can choose a branch WITHOUT opening it;
    a wider page is only affordable if each entry says enough to skip
    the ones that do not matter. Source files are named once, on the leaf
    that holds them, not sampled again on every page above it.
    """
    link = f"- [{title}]({_name(child, stems)}/brief.md)"
    summary = _summary(conn, child)
    return f"{link} — {summary}" if summary else link


def _summary(conn: sqlite3.Connection, node_id: int) -> str:
    """The brief's first sentence of prose that is not already its title."""
    title = heading(conn, node_id)
    prose = " ".join(
        _EMPHASIS.sub("", line.strip())
        for line in _brief_text(conn, node_id).splitlines()
        if line.strip() and not line.lstrip().startswith(_NOT_PROSE)
    )
    for said in re.split(r"(?<=[.!?])\s+", prose):
        if said and not unframe(said).startswith(title.removesuffix("…")):
            return sentence(said, _SUMMARY_CHARS)
    return ""


def _sources(conn: sqlite3.Connection, section_ids: tuple[int, ...]) -> str:
    """A leaf's source files, each once, grouped under the source they are in.

    A path is relative to its source's repository, which the reading agent has
    checked out; the source's name and commit head each group once instead of
    repeating on every line.
    """
    groups: dict[str, list[str]] = {}
    for sid in section_ids:
        row = conn.execute(
            "SELECT source, path, version FROM sections WHERE id = ?", (sid,)
        ).fetchone()
        if row is None:
            continue
        version = str(row["version"] or "")[:7]
        where = f"{row['source']} @ {version}" if version else row["source"]
        paths = groups.setdefault(where, [])
        if row["path"] not in paths:
            paths.append(row["path"])
    return "\n\n".join(
        f"{where}:\n\n" + "\n".join(f"- `{p}`" for p in paths)
        for where, paths in groups.items()
    )


def _directory(
    node_id: int,
    parent: Mapping[int, int],
    root: int,
    stems: Mapping[int, str],
) -> str:
    # the chain of names from the root down to this node, root excluded — so
    # only the ROOT is "" and every other node, parentless or not, gets its own
    # id-suffixed directory. A parentless non-root node is a defect (the loader
    # refuses a forest at the TOP level; a lower-level orphan still loads and
    # renders into an unlinked directory), but the renderer stays total: it can
    # never collide two briefs onto one key, and it can never emit a leading
    # slash.
    parts: list[str] = []
    cur = node_id
    while cur != root:
        parts.append(_name(cur, stems))
        above = parent.get(cur)
        if above is None:
            break
        cur = above
    return "/".join(reversed(parts))


def _brief_text(conn: sqlite3.Connection, node_id: int) -> str:
    row = briefs.get(conn, node_id)
    return row["text"] if row is not None else ""


def _name(node_id: int, stems: Mapping[int, str]) -> str:
    # append the node id so sibling briefs with the same heading (LLM briefs
    # readily repeat "Overview" etc.) never collide onto one directory and drop
    # a subtree — the same collision-safety sections already have.
    return f"{stems[node_id]}-{node_id}"


def _stems(conn: sqlite3.Connection, tree: ExportTree) -> dict[int, str]:
    """What each node's directory is called before its id.

    Siblings whose titles slug alike (a weak model opens two briefs with the
    same clause) would differ by a number alone, which tells an agent nothing
    about which to open. Each of them is named by what it says after the
    title, its own summary, when that tells them apart.
    """
    stems = {
        node_id: slug(heading(conn, node_id)) or "node"
        for node_id in tree.nodes
    }
    for node in tree.nodes.values():
        alike: dict[str, list[int]] = {}
        for child in node.children:
            alike.setdefault(stems[child], []).append(child)
        for shared in alike.values():
            if len(shared) > 1:
                others = {
                    stems[child]
                    for child in node.children
                    if child not in shared
                }
                stems |= _tell_apart(conn, shared, others)
    return stems


def _tell_apart(
    conn: sqlite3.Connection, shared: list[int], others: set[str]
) -> dict[int, str]:
    """The new stems of ``shared``, or none when they would not help.

    A stem taken from a summary may equal a sibling's own stem; that would
    make a new shared stem, so the titles stay.
    """
    said = {node: slug(_summary(conn, node)) for node in shared}
    stems = set(said.values())
    if "" in stems or len(stems) < len(said) or stems & others:
        return {}
    return said


def _section_heading(conn: sqlite3.Connection, section_id: int) -> str:
    row = conn.execute(
        "SELECT path FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    return row["path"] if row is not None else f"section {section_id}"


_SUMMARY_CHARS = 160
_NOT_PROSE = ("#", "-", "*", "|", ">", "```")
_EMPHASIS = re.compile(r"[*_`]+")
