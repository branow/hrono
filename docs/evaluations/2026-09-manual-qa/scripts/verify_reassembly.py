"""Verify the two byte-identity invariants the spec promises.

1. a section body == concatenation of its passages' bodies, in ordinal order
2. a file's sections, concatenated in ordinal order == the original file bytes
   in the sync cache

Usage: python verify_reassembly.py <db_path> <cache_root>
Writes artifacts/reassembly-report.md.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    db_path, cache_root = sys.argv[1], Path(sys.argv[2])
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    section_fail: list[str] = []
    file_fail: list[str] = []
    missing_cache: list[str] = []
    checked_sections = 0
    checked_files = 0

    sections = list(
        conn.execute(
            "SELECT s.id, s.source, s.path, s.ordinal, s.byte_start, "
            "s.byte_end, c.body FROM sections s JOIN contents c "
            "ON c.content_hash = s.content_hash ORDER BY s.source, s.path, "
            "s.ordinal"
        )
    )
    for row in sections:
        checked_sections += 1
        parts = [
            item["body"]
            for item in conn.execute(
                "SELECT c.body FROM passages p JOIN contents c "
                "ON c.content_hash = p.content_hash WHERE p.section_id = ? "
                "ORDER BY p.ordinal",
                (row["id"],),
            )
        ]
        if b"".join(parts) != row["body"]:
            section_fail.append(
                f"section {row['id']} {row['source']}:{row['path']}"
                f"#{row['ordinal']} passages={len(parts)} "
                f"joined={len(b''.join(parts))} body={len(row['body'])}"
            )

    by_file: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in sections:
        by_file.setdefault((row["source"], row["path"]), []).append(row)

    for (source, path), rows in sorted(by_file.items()):
        cache = cache_root / source / path
        if not cache.exists():
            missing_cache.append(f"{source}:{path}")
            continue
        checked_files += 1
        joined = b"".join(
            r["body"] for r in sorted(rows, key=lambda r: r["ordinal"])
        )
        original = cache.read_bytes()
        if joined != original:
            file_fail.append(
                f"{source}:{path} sections={len(rows)} "
                f"joined={len(joined)} original={len(original)}"
            )

    lines = [
        "# byte-identity verification",
        "",
        f"- sections checked: {checked_sections}",
        f"- section == sum(passages): {'PASS' if not section_fail else 'FAIL'}"
        f" ({len(section_fail)} mismatches)",
        f"- files checked: {checked_files}",
        f"- file == sum(sections): {'PASS' if not file_fail else 'FAIL'}"
        f" ({len(file_fail)} mismatches)",
        f"- files whose cache copy was not found: {len(missing_cache)}",
        "",
    ]
    for title, items in (
        ("section mismatches", section_fail),
        ("file mismatches", file_fail),
        ("cache not found", missing_cache),
    ):
        if items:
            lines += [f"## {title}", ""] + [f"- {i}" for i in items[:40]] + [""]

    text = "\n".join(lines)
    (ROOT / "artifacts" / "reassembly-report.md").write_text(
        text, encoding="utf-8"
    )
    print(text)


if __name__ == "__main__":
    main()
