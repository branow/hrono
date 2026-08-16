from pathlib import Path

from hrono.ingest.filter import ingestable


def tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("print('hi')\n")
    (root / "README.md").write_text("# readme\n")
    (root / "node_modules" / "dep").mkdir(parents=True)
    (root / "node_modules" / "dep" / "index.js").write_text("x")
    (root / "poetry.lock").write_text("locked")
    (root / "bin.dat").write_bytes(b"head\x00tail")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n")


def test_keeps_text_drops_glob_binary_and_git(tmp_path: Path) -> None:
    tree(tmp_path)
    kept = ingestable(tmp_path, None)
    assert kept == ("README.md", "src/app.py")


def test_excludes_are_glob_matched(tmp_path: Path) -> None:
    tree(tmp_path)
    kept = ingestable(tmp_path, None)
    assert "node_modules/dep/index.js" not in kept
    assert "poetry.lock" not in kept


def test_null_byte_file_is_dropped_as_binary(tmp_path: Path) -> None:
    tree(tmp_path)
    assert "bin.dat" not in ingestable(tmp_path, None)


def test_git_metadata_is_never_included(tmp_path: Path) -> None:
    tree(tmp_path)
    assert all(not p.startswith(".git") for p in ingestable(tmp_path, None))


def test_size_cap_drops_oversize_files(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("a" * 500)
    (tmp_path / "small.txt").write_text("a" * 10)
    kept = ingestable(tmp_path, {"max_size_mb": 0.0001})  # ~104 byte cap
    assert kept == ("small.txt",)


def test_custom_exclude_overrides_default(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    kept = ingestable(tmp_path, {"exclude": ["**/b.py"]})
    assert kept == ("a.py",)


def test_result_is_deterministic_and_sorted(tmp_path: Path) -> None:
    for name in ("c.txt", "a.txt", "b.txt"):
        (tmp_path / name).write_text("x")
    assert ingestable(tmp_path, None) == ("a.txt", "b.txt", "c.txt")


def test_default_cap_keeps_normal_files(tmp_path: Path) -> None:
    (tmp_path / "normal.py").write_text("def f():\n    return 1\n")
    assert ingestable(tmp_path, None) == ("normal.py",)


def test_symlink_escaping_the_cache_is_never_ingested(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "real.py").write_text("kept")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret outside the cache")
    (cache / "abs_escape").symlink_to(outside)
    (cache / "rel_escape").symlink_to(Path("../outside.txt"))
    kept = ingestable(cache, None)
    assert kept == ("real.py",)
    assert "abs_escape" not in kept
    assert "rel_escape" not in kept


def test_symlink_to_a_file_inside_the_cache_is_also_skipped(
    tmp_path: Path,
) -> None:
    (tmp_path / "real.py").write_text("x")
    (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
    assert ingestable(tmp_path, None) == ("real.py",)
