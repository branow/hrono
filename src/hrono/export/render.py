"""Render the collapsed agent-facing tree to a path -> markdown mapping.

Per agent node: its stored brief text as-is (already ends with its
Caution section; never regenerated), its member references re-attached from the
metadata they are stored in, then a MECHANICAL child listing rendered
from the collapsed tree in code (titles + relative links, no LLM, no
hallucinated links; each entry below the root also links a few of the section
files beneath it). Leaf nodes list their sections; each section is rendered to
its own file, reassembled byte-identically from its stored passages with
an address header. Human notes render only when
passed. No file I/O — returns a deterministic path -> content map
that the caller materialises into a folder tree.

Every key is RELATIVE and unique. The root's own brief is ``root.md``
and its sections sit beside it at the top level; every other node owns an
id-suffixed directory, so no path can start with "/" (which pathlib would let
reroot the whole export out of the output folder) and no two briefs can land on
one key.
"""

from __future__ import annotations

import json
import posixpath
import re
import sqlite3
from collections.abc import Callable, Mapping
from itertools import chain, zip_longest
from pathlib import Path

from hrono.export.citations import FactIndex, cite, settling
from hrono.export.collapse import ExportNode, ExportTree
from hrono.ingest.split.constants import section_budget
from hrono.ingest.store import get_content
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
    directories = {
        node_id: _directory(node_id, parent, tree.root, stems)
        for node_id in tree.nodes
    }
    where = {
        section_id: _under(
            directories[node_id], _section_name(conn, section_id)
        )
        for node_id, node in tree.nodes.items()
        for section_id in node.sections
    }
    bodies = {
        sid: _reassemble(conn, sid).decode("utf-8", "replace") for sid in where
    }

    index = FactIndex({where[sid]: body for sid, body in bodies.items()})
    for node_id in sorted(tree.nodes):
        node = tree.nodes[node_id]
        directory = directories[node_id]
        path = "root.md" if node_id == tree.root else _under(directory, "brief")
        under = {where[sid] for sid in _subtree_sections(tree, node_id)}
        text = _brief_text(conn, node_id)
        if node.children:  # cite only what the index page keeps
            text = _routing(text)
        start = posixpath.dirname(path) or "."
        files[path] = _node_markdown(
            conn,
            tree,
            node_id,
            notes.get(node_id),
            _cited(text, index, under, path),
            stems,
            lambda child, leads, start=start: _leads_to(
                conn,
                tree,
                child,
                where,
                start,
                _settling(conn, tree, child, where, index),
                leads,
            ),
        )
        for section_id in node.sections:
            files[where[section_id]] = _section_markdown(
                conn, section_id, bodies[section_id]
            )
    return files


def _subtree_sections(tree: ExportTree, node_id: int) -> tuple[int, ...]:
    node = tree.nodes[node_id]
    return node.sections + tuple(
        section
        for child in node.children
        for section in _subtree_sections(tree, child)
    )


def _cited(text: str, index: FactIndex, within: set[str], page: str) -> str:
    """The brief with its facts linked to the section pages that state them."""
    start = posixpath.dirname(page) or "."
    return cite(
        text,
        index,
        link=lambda path: posixpath.relpath(path, start),
        within=within,
    )


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
    leads_to: Callable[[int, int], str],
) -> str:
    node = tree.nodes[node_id]
    parts = [brief.rstrip()]
    if node.children:
        called = names(conn, node.children)

        def listing(leads: int) -> str:
            return "\n".join(
                _child_entry(
                    conn, child, called[child], stems, leads_to(child, leads)
                )
                for child in node.children
            )

        # as many section links per entry as keep the page within one
        # SECTION: a page at full WIDTH cannot afford any
        # (the page is the parts joined by a blank line, the Children list
        # and the human note among them, and a closing newline)
        after = [f"## Notes\n\n{note}"] if note else []
        base = (
            len("\n\n".join([*parts, "## Children\n", "", *after]).encode()) + 1
        )
        # the root carries no links: every turn of every session reads it,
        # and what it spent on them cost the grep arm more than the walk
        # arm saved
        for leads in range(0 if node_id == tree.root else _LEADS, 0, -1):
            children = listing(leads)
            if base + len(children.encode()) <= _PAGE_BYTES:
                break
        else:
            children = listing(0)
        parts.append("## Children\n")
        parts.append(children)
    elif node.sections:
        parts.append("## Sections\n")
        parts.append(
            "\n".join(
                f"- [{_section_heading(conn, sid)}]"
                f"({_section_name(conn, sid)}.md)"
                for sid in node.sections
            )
        )
    if note:
        parts.append(f"## Notes\n\n{note}")
    if node.level == tree.levels - 1:  # a LEAF: its members are source URIs
        references = _references(conn, node_id)
        if references:
            parts.append(references)
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
    leads: str,
) -> str:
    """An index page's entry: title, link, what the child holds, where to read.

    The summary is there so an agent can choose a branch WITHOUT opening it;
    a wider page is only affordable if each entry says enough to skip
    the ones that do not matter. ``leads`` names section files beneath the
    child, so an agent that has chosen can open the answer from the index.
    """
    link = f"- [{title}]({_name(child, stems)}/brief.md)"
    summary = _summary(conn, child)
    entry = f"{link} — {summary}" if summary else link
    return f"{entry}\n  {leads}" if leads else entry


def _leads_to(
    conn: sqlite3.Connection,
    tree: ExportTree,
    child: int,
    where: Mapping[int, str],
    start: str,
    settles: list[int],
    limit: int,
) -> str:
    """Up to ``limit`` section files beneath ``child``, linked from ``start``.

    The sections the child's own brief drew its facts from come first
    (``settles``); the rest are taken in turn from each node of the subtree
    that holds sections, so a child with many leaves shows several of them
    rather than the first one's run, and a file split into several sections is
    named once. The count of the rest says the list is a sample.
    """
    held = [
        node.sections for node in _descendants(tree, child) if node.sections
    ]
    shown = _distinct_files(
        conn,
        settles
        + [sid for sid in chain.from_iterable(zip_longest(*held)) if sid],
    )[:limit]
    if not shown:
        return ""
    links = ", ".join(
        f"[{_short(_section_heading(conn, sid))}]"
        f"({posixpath.relpath(where[sid], start)})"
        for sid in shown
    )
    rest = sum(map(len, held)) - len(shown)
    return f"Sections: {links}" + (f" and {rest} more" if rest else "")


def _settling(
    conn: sqlite3.Connection,
    tree: ExportTree,
    child: int,
    where: Mapping[int, str],
    index: FactIndex,
) -> list[int]:
    under = {where[sid]: sid for sid in _subtree_sections(tree, child)}
    return [
        under[label]
        for label in settling(_brief_text(conn, child), index, set(under))
    ]


def _distinct_files(
    conn: sqlite3.Connection, section_ids: list[int]
) -> list[int]:
    """The first section of each file: a long file is several sections."""
    seen: set[str] = set()
    first: list[int] = []
    for sid in section_ids:
        path = _section_heading(conn, sid)
        if path not in seen:
            seen.add(path)
            first.append(sid)
    return first


def _short(path: str) -> str:
    """The last two parts of a path: the link already carries the rest."""
    return "/".join(path.split("/")[-2:])


def _descendants(tree: ExportTree, node_id: int) -> list[ExportNode]:
    node = tree.nodes[node_id]
    return [node] + [
        below for child in node.children for below in _descendants(tree, child)
    ]


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


def _references(conn: sqlite3.Connection, node_id: int) -> str:
    """Re-attach a LEAF's member list, which is stored beside its text.

    It lives outside ``briefs.text`` so a lexically dense path list stays out of
    the vector index and FTS, which would read it as prose; a leaf's list is its
    members' source URIs — provenance the export shows nowhere else — so this is
    where it is put back.

    An UPPER node's list is child NODE IDS, and the caller skips it there for
    two reasons: ``## Children`` already renders those children as titled links,
    so it would be the same thing twice in the same file; and an id is only
    meaningful while that node exists, so a brief written before a rebuild would
    have the map cite topics that have since been retired.

    The caller keys that on the node's LEVEL, not on whether it has children.
    They differ in exactly one state, and it is a real one: a childless
    upper node, left when a rebuild re-mints the leaf ids and cascades the
    root's edges away. Such a root has no children to render, so a child-count
    guard calls it a leaf and prints its stored ids — three of which had been
    retired in a ~120-section test corpus. Level is the property the member
    list actually depends on.
    """
    row = briefs.get(conn, node_id)
    members = json.loads(row["members"]) if row is not None else []
    if not members:
        return ""
    listed = "\n".join(f"- {member}" for member in members)
    return f"## References\n\n{listed}"


def _section_markdown(
    conn: sqlite3.Connection, section_id: int, body: str
) -> str:
    row = conn.execute(
        "SELECT path, uri FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    return f"# {row['path']}\n\n<!-- {row['uri']} -->\n\n{body}"


def _reassemble(conn: sqlite3.Connection, section_id: int) -> bytes:
    rows = conn.execute(
        "SELECT content_hash FROM passages WHERE section_id = ? "
        "ORDER BY ordinal, id",
        (section_id,),
    ).fetchall()
    return b"".join(
        get_content(conn, row["content_hash"]) or b"" for row in rows
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


def _section_name(conn: sqlite3.Connection, section_id: int) -> str:
    return f"{slug(_section_heading(conn, section_id))}-{section_id}"


_SUMMARY_CHARS = 160
_LEADS = 3
_PAGE_BYTES = section_budget(Path("index.md"))  # one SECTION
_NOT_PROSE = ("#", "-", "*", "|", ">", "```")
_EMPHASIS = re.compile(r"[*_`]+")
