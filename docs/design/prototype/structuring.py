"""Structure-aware paragraph splitting — the settled recipe from structure-split.ipynb.

A file becomes a structure tree (tree-sitter grammar per extension; files without
a grammar get a synthetic tree built by the delimiter cascade), and one packer
walks it: consecutive siblings pack into a paragraph while they fit, an oversized
node is descended into, an oversized structureless span grows synthetic delimiter
levels (blank-line -> line -> sentence -> comma -> word), and byte-chop is the
last resort for a span with no delimiters at all. Structural crumbs merge into
the preceding paragraph.

Each paragraph carries struct_paths: a LIST of full paths, one per structure
node packed into it (usually one). A path is the chain of structure nodes from
the file root, each segment {"type", "name"?, "idx"} where idx disambiguates
siblings sharing the same type+name (overloads, duplicate keys, repeated
headings). Shared ancestors duplicate across paths — uniform beats clever.
Synthetic segments are typed "~<delimiter>"; chop pieces get a final
{"type": "raw", "part": k, "of": n} segment.
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter_language_pack import get_parser

with open(Path(__file__).parent / "structuring.toml", "rb") as _f:
    _cfg = tomllib.load(_f)

BUDGET = _cfg["budgets"]["paragraph_bytes"]
CHUNK_BUDGET = _cfg["budgets"]["chunk_bytes"]
MIN_PARA = _cfg["budgets"]["min_para"]
MIN_GROUP = _cfg["budgets"]["min_group"]
DELIMS = [s.encode() for s in _cfg["delimiters"]["cascade"]]
SEP_NAMES = _cfg["delimiters"]["names"]

LANG_BY_EXT = {
    ".py": "python", ".java": "java", ".kt": "kotlin", ".js": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "tsx", ".go": "go",
    ".rb": "ruby", ".rs": "rust", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".hpp": "cpp", ".cs": "csharp", ".php": "php", ".sh": "bash", ".sql": "sql",
    ".gradle": "groovy", ".groovy": "groovy",
    ".md": "markdown", ".mdx": "markdown", ".html": "html",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".xml": "xml",
}

_parsers: dict = {}


@dataclass
class Paragraph:
    """A packed span. Used at both levels: paragraphs (~800 B) and chunks (~10 KB) —
    same mechanism, different budget. For chunk-level spans, `paragraphs` holds the
    sub-spans packed inside it; `group`/`trail` are internal packer state enabling
    that second-level pack."""

    byte_start: int
    byte_end: int
    struct_paths: list = field(default_factory=list)  # list of FULL paths, one per packed node
    group: list = field(default_factory=list, repr=False)   # structure nodes packed into this span
    trail: tuple = ()                                        # shared ancestor chain (internal)
    paragraphs: list | None = None                           # sub-spans (chunk level only)

    @property
    def synthetic(self) -> bool:
        return any(s["type"].startswith("~") or s["type"] == "raw"
                   for path in self.struct_paths for s in path)


class Block:
    """Synthetic structure node for spans the parser gave no children for."""

    def __init__(self, start, end, children=(), label="text"):
        self.start_byte, self.end_byte, self.children = start, end, list(children)
        self.label = label
        self.text = b""   # name extraction never applies to synthetic nodes
        self.ordinal = None  # position among build-time siblings (idx source, wrapper-proof)


def parser_for(path: Path):
    lang = LANG_BY_EXT.get(path.suffix.lower())
    if lang is None:
        return None, "plain"
    if lang not in _parsers:
        try:
            _parsers[lang] = get_parser(lang)
        except Exception:
            _parsers[lang] = None
    return _parsers[lang], (lang if _parsers[lang] else "plain")


def deepen(raw: bytes, start: int, end: int, level: int = 0) -> list:
    """Text delimiters as structure builders — grows the tree only; all
    budgeting stays in the packer."""
    if level >= len(DELIMS):
        return []
    sep = DELIMS[level]
    kids, pos = [], start
    for part in raw[start:end].split(sep):
        pend = pos + len(part)
        span_end = min(pend + len(sep), end)
        if part.strip():
            sub = deepen(raw, pos, span_end, level + 1) if span_end - pos > BUDGET else []
            kids.append(Block(pos, span_end, sub, label=SEP_NAMES[level]))
        pos = pend + len(sep)
    if len(kids) < 2:
        return deepen(raw, start, end, level + 1)
    for i, k in enumerate(kids):
        k.ordinal = i
    return kids


def node_type(node) -> str:
    return f"~{node.label}" if isinstance(node, Block) else node.type


def node_name(node) -> str | None:
    """Best-effort display name of a structure node, per grammar family."""
    if isinstance(node, Block):
        return None
    for fld in ("name", "key"):  # java/ts/python declarations; json pairs
        child = node.child_by_field_name(fld)
        if child is not None:
            return child.text.decode("utf-8", "replace").strip('"')[:80]
    if node.type == "section" and node.children:  # markdown: heading text
        head = node.children[0]
        if "heading" in head.type:
            return head.text.decode("utf-8", "replace").lstrip("#").strip()[:80]
    if node.type == "element":  # xml: tag name from <tag ...>
        m = re.match(rb"<\s*([\w:.-]+)", node.text)
        if m:
            return m.group(1).decode()
    if node.type == "command" and node.children:  # groovy DSL: `dependencies { ... }`
        head = node.children[0]                    # command -> block -> unit holds the name
        if head.type == "block" and head.children:
            head = head.children[0]
        if head.type in ("unit", "identifier"):
            return head.text.decode("utf-8", "replace")[:80]
    return None


def seg(node, siblings) -> dict:
    """Path segment with idx = position among same-type+name siblings. idx always
    comes from the node's TRUE sibling list (AST parent / build-time ordinal), so
    re-packing a subset of nodes (chunk wrappers) can't shift it."""
    if isinstance(node, Block):
        return {"type": node_type(node), "idx": node.ordinal or 0}
    name = node_name(node)
    sibs = node.parent.children if node.parent is not None else siblings
    same = [s for s in sibs if node_type(s) == node_type(node) and node_name(s) == name]
    d = {"type": node_type(node)}
    if name is not None:
        d["name"] = name
    d["idx"] = same.index(node)
    return d


def pack(node, raw: bytes, budget: int, trail: tuple = (),
         min_group: int | None = None) -> list[Paragraph]:
    """min_group: flush a sibling group once it reaches this size — budget stays
    the hard max, but structural units >= min_group stand alone instead of being
    greedily packed with unrelated siblings. None = fill greedily to budget."""
    min_group = budget if min_group is None else min_group
    kids = list(node.children) or deepen(raw, node.start_byte, node.end_byte)
    if not kids:  # no structure, no delimiters: chop, marked as raw parts
        spans = [(s, min(s + budget, node.end_byte))
                 for s in range(node.start_byte, node.end_byte, budget)]
        return [Paragraph(s, e, [list(trail) + [{"type": "raw", "part": k + 1, "of": len(spans)}]],
                          trail=tuple(trail))
                for k, (s, e) in enumerate(spans)]

    paras: list[Paragraph] = []
    group_start, group_kids = None, []

    def flush(end: int) -> None:
        nonlocal group_start, group_kids
        if group_start is None:
            return
        whole_node = group_start <= kids[0].start_byte and end >= node.end_byte
        if whole_node and len(group_kids) > 1:
            paths = [list(trail)]  # the whole node: its own trail says it all
        else:
            # one full path per member; shared ancestors duplicate — uniform beats
            # clever. Preference order: content members (named, or big enough to
            # matter) > any word-typed member (unnamed runs: imports, statements —
            # typed+idx segs keep paths positional) > bare trail (pure punctuation).
            members = [k for k in group_kids if re.search(r"\w", node_type(k))]
            content = [k for k in members
                       if node_name(k) or k.end_byte - k.start_byte >= MIN_PARA]
            chosen = content or members
            paths = ([list(trail) + [seg(k, kids)] for k in chosen]
                     if chosen else [list(trail)])
        new_trail = tuple(paths[0]) if len(group_kids) == 1 else tuple(trail)
        paras.append(Paragraph(group_start, end, paths, group=list(group_kids), trail=new_trail))
        group_start, group_kids = None, []

    for i, child in enumerate(kids):
        nxt_start = kids[i + 1].start_byte if i + 1 < len(kids) else node.end_byte
        if nxt_start - child.start_byte > budget:  # child alone busts the budget
            flush(child.start_byte)
            sub = pack(child, raw, budget, tuple(trail) + (seg(child, kids),), min_group)
            if sub and sub[-1].byte_end < nxt_start:  # trailing gap rides along
                sub[-1].byte_end = nxt_start
            paras += sub
            continue
        if group_start is None:
            group_start, group_kids = child.start_byte, [child]
        elif nxt_start - group_start > budget:  # group would bust: flush before child
            flush(child.start_byte)
            group_start, group_kids = child.start_byte, [child]
        else:
            group_kids.append(child)
        if nxt_start - group_start >= min_group:  # group can stand alone: flush at the boundary
            flush(nxt_start)
    flush(node.end_byte)
    return paras


def merge_tiny(paras: list[Paragraph], min_size: int = MIN_PARA) -> list[Paragraph]:
    """Structural crumbs merge into the preceding paragraph (struct kept from
    the survivor); a tiny first paragraph merges forward instead."""
    out: list[Paragraph] = []
    for p in paras:
        if out and p.byte_end - p.byte_start < min_size:
            out[-1].byte_end = p.byte_end
        else:
            out.append(p)
    if len(out) > 1 and out[0].byte_end - out[0].byte_start < min_size:
        out[1].byte_start = out[0].byte_start
        out.pop(0)
    return out


def split_file(path: Path) -> tuple[str, list[Paragraph]]:
    """Split one file into paragraphs. Returns (format, paragraphs); paragraphs
    are contiguous-ish byte spans covering all non-blank content of the file."""
    raw = path.read_bytes()
    parser, fmt = parser_for(path)
    if len(raw) <= BUDGET:
        return (fmt, [Paragraph(0, len(raw))]) if raw.strip() else (fmt, [])
    root = parser.parse(raw).root_node if parser else Block(0, len(raw), deepen(raw, 0, len(raw)))
    paras = [p for p in pack(root, raw, BUDGET) if raw[p.byte_start:p.byte_end].strip()]
    paras = merge_tiny(paras)
    if paras:
        paras[0].byte_start = 0
    return fmt, paras


def split_file_hier(path: Path, chunk_budget: int = CHUNK_BUDGET,
                    para_budget: int = BUDGET) -> tuple[str, list[Paragraph]]:
    """Hierarchical split: the SAME packer runs twice over the same structure
    tree — first at chunk_budget producing chunks (each with its own
    struct_paths), then at para_budget inside each chunk's node group, so
    paragraph boundaries nest inside chunk boundaries by construction.
    Returns (format, chunks); each chunk has .paragraphs filled."""
    raw = path.read_bytes()
    parser, fmt = parser_for(path)
    if not raw.strip():
        return fmt, []
    if len(raw) <= para_budget:
        chunk = Paragraph(0, len(raw), paragraphs=[Paragraph(0, len(raw))])
        return fmt, [chunk]
    root = parser.parse(raw).root_node if parser else Block(0, len(raw), deepen(raw, 0, len(raw)))

    chunks = [c for c in pack(root, raw, chunk_budget) if raw[c.byte_start:c.byte_end].strip()]
    chunks = merge_tiny(chunks)
    chunks[0].byte_start = 0

    for c in chunks:
        if c.byte_end - c.byte_start <= para_budget:
            c.paragraphs = [Paragraph(c.byte_start, c.byte_end,
                                      [list(path) for path in c.struct_paths], trail=c.trail)]
            continue
        group = c.group
        if len(group) == 1:  # chunk == one node whose seg is already the trail's tail:
            group = list(group[0].children)  # descend from its children, else the seg duplicates
        wrapper = Block(c.byte_start, c.byte_end, group)  # empty group -> delimiter deepening
        paras = [p for p in pack(wrapper, raw, para_budget, trail=c.trail, min_group=MIN_GROUP)
                 if raw[p.byte_start:p.byte_end].strip()]
        paras = merge_tiny(paras)
        paras[0].byte_start = c.byte_start
        paras[-1].byte_end = c.byte_end
        c.paragraphs = paras

    return fmt, chunks


def sp_render(path: list[dict]) -> str:
    """One struct path as a compact sp: URI — reversible, space-free.

    Segment = percent-encoded name, or "." + type when unnamed (the leading dot
    means "type, not name"; names starting with "."/"~" get that char encoded).
    "[i]" appended only when idx > 0; raw chops carry "[part/of]".
    """
    from urllib.parse import quote
    parts = []
    for s in path:
        if "name" in s:
            label = quote(s["name"], safe="")
            if label[:1] in (".", "~"):
                label = f"%{ord(label[0]):02X}" + label[1:]
        else:
            label = "." + s["type"]
        if "part" in s:
            label += f"[{s['part']}/{s['of']}]"
        elif s.get("idx"):
            label += f"[{s['idx']}]"
        parts.append(label)
    return "sp:/" + "/".join(parts)


def rag_header(uri: str, struct_paths: list[list[dict]]) -> str:
    """The one-line header injected above a RAG fragment: URI, then each
    struct path, space-separated."""
    return " ".join([uri] + [sp_render(p) for p in struct_paths])
