"""Mechanical faithfulness check for condensations and summaries - no LLM.

Extracts identifier-like tokens (camelCase, PascalCase, dotted/hyphenated
compounds, multi-digit numbers) from each generated text and verifies every one
literally appears in the source content it was generated from. A token missing
from the source is a suspected fabrication - the "photo max 512 chars" class of
error, caught deterministically.

Usage: uv run python check_faithfulness.py
"""

import json
import re
import sys
from pathlib import Path

HRONO_DIR = Path(".hrono")
SAMPLES_DIR = HRONO_DIR / "summarization-samples"
EXPERIMENTS_DIR = HRONO_DIR / "summarization-experiments"
MAP_CACHE_DIR = EXPERIMENTS_DIR / "map-cache"

IDENTIFIER_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:[./][A-Za-z0-9_$#{}-]+)+"   # dotted/path compounds
    r"|\b[a-z]+(?:[A-Z][a-z0-9]*)+\b"                      # camelCase
    r"|\b(?:[A-Z][a-z0-9]+){2,}\b"                         # PascalCase (2+ humps)
    r"|\b[A-Za-z]+_[A-Za-z0-9_]+\b"                        # snake_case
    r"|\b\d{3,}\b"                                          # numbers with 3+ digits
)


def main() -> None:
    problems = 0
    problems += check_condensations()
    problems += check_summaries()
    print(f"\n{'FAIL' if problems else 'OK'}: {problems} text(s) with suspect tokens")
    sys.exit(1 if problems else 0)


def check_condensations() -> int:
    """Each map-stage condensation against its single source chunk."""
    print("== condensations (map stage) ==")
    problems = 0
    for cluster_dir in sorted(SAMPLES_DIR.glob("cluster-*")):
        meta = json.loads((cluster_dir / "meta.json").read_text())
        sources = load_chunk_texts(cluster_dir)
        for ordinal, member in enumerate(meta["members"]):
            call_file = MAP_CACHE_DIR / f"{member['hash']}.call.json"
            if not call_file.exists():
                continue
            call = json.loads(call_file.read_text())
            missing = missing_tokens(call["response"], sources[ordinal])
            if missing:
                problems += 1
                print(f"  SUSPECT {cluster_dir.name} {call['chunk_label'][:60]}: {sorted(missing)[:8]}")
    if not problems:
        print("  all clean")
    return problems


def check_summaries() -> int:
    """Each experiment summary against the full content of its cluster."""
    print("== summaries (experiments) ==")
    problems = 0
    for cluster_dir in sorted(EXPERIMENTS_DIR.glob("cluster-*")):
        cluster_id = cluster_dir.name.removeprefix("cluster-")
        sample_dir = SAMPLES_DIR / cluster_dir.name
        if not sample_dir.exists():
            continue
        full_content = "\n".join(load_chunk_texts(sample_dir))
        for summary_file in sorted(cluster_dir.glob("*.md")):
            missing = missing_tokens(summary_file.read_text(), full_content)
            if missing:
                problems += 1
                print(f"  SUSPECT cluster-{cluster_id} {summary_file.stem}: {sorted(missing)[:8]}")
    if not problems:
        print("  all clean")
    return problems


def missing_tokens(generated: str, source: str) -> set[str]:
    """Tokens in the generated text with no literal (case-insensitive) support
    in the source. Slash-joined prose compounds count as supported when every
    part is supported."""
    source_lower = source.lower()
    missing = set()
    for token in IDENTIFIER_RE.findall(generated):
        parts = token.rstrip(".").split("/")
        if all(p.lower() in source_lower for p in parts if p):
            continue
        missing.add(token)
    return missing


def load_chunk_texts(sample_dir: Path) -> list[str]:
    """Chunk label + content, since generated texts legitimately cite labels."""
    return [f"{p.stem}\n{p.read_text(errors='replace')}"
            for p in sorted((sample_dir / "chunks").iterdir())]


if __name__ == "__main__":
    main()
