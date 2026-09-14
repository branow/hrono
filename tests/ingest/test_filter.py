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


def test_custom_exclude_extends_the_defaults(tmp_path: Path) -> None:
    # F4: a source that excludes one directory of its own used to LOSE
    # node_modules and lockfile protection, silently, at LLM cost.
    tree(tmp_path)
    (tmp_path / "b.py").write_text("x")
    kept = ingestable(tmp_path, {"exclude": ["**/b.py"]})
    assert kept == ("README.md", "src/app.py")
    assert "node_modules/dep/index.js" not in kept
    assert "poetry.lock" not in kept


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


def assets(root: Path) -> None:
    (root / "media").mkdir(parents=True)
    (root / "media" / "logo.svg").write_text("<svg><path d='M0 0'/></svg>")
    (root / "media" / "favicon.ico").write_text("icon")
    (root / "media" / "font.woff2").write_text("font")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# guide\n")
    (root / "data.csv").write_text("a,b\n1,2\n")
    (root / "app.min.js").write_text("var a=1")
    (root / "app.js").write_text("var a = 1\n")
    (root / "bundle.js.map").write_text("{}")
    (root / "vendor").mkdir()
    (root / "vendor" / "dep.go").write_text("package dep\n")
    (root / "api_pb2.py").write_text("# generated\n")
    (root / "client.generated.ts").write_text("// generated\n")
    (root / "main.py").write_text("print(1)\n")


def test_assets_and_generated_code_are_ignored_by_default(
    tmp_path: Path,
) -> None:
    # F5: 12 of 92 sections in the QA run were SVG path data, 13% of the
    # corpus AND of the condense spend, and they clustered into a junk topic.
    assets(tmp_path)
    kept = ingestable(tmp_path, None)
    assert kept == ("app.js", "docs/guide.md", "main.py")


def test_an_include_pattern_re_admits_one_ignored_file(tmp_path: Path) -> None:
    assets(tmp_path)
    kept = ingestable(tmp_path, {"include": ["**/logo.svg"]})
    assert "media/logo.svg" in kept
    assert "media/favicon.ico" not in kept  # only what was asked for
    assert "data.csv" not in kept


def test_include_generated_re_admits_the_generated_group_only(
    tmp_path: Path,
) -> None:
    assets(tmp_path)
    kept = ingestable(tmp_path, {"include_generated": True})
    assert "api_pb2.py" in kept
    assert "client.generated.ts" in kept
    assert "media/logo.svg" not in kept  # other groups still ignored
    assert "vendor/dep.go" not in kept


def test_replace_defaults_hands_the_list_to_the_caller(tmp_path: Path) -> None:
    assets(tmp_path)
    kept = ingestable(
        tmp_path, {"replace_defaults": True, "exclude": ["**/*.csv"]}
    )
    assert "media/logo.svg" in kept  # baked groups dropped wholesale
    assert "vendor/dep.go" in kept
    assert "data.csv" not in kept  # the caller's own list still applies


def test_a_users_exclude_beats_their_include(tmp_path: Path) -> None:
    assets(tmp_path)
    kept = ingestable(
        tmp_path, {"exclude": ["**/logo.svg"], "include": ["**/*.svg"]}
    )
    assert "media/logo.svg" not in kept


def test_ignored_extensions_match_case_insensitively(tmp_path: Path) -> None:
    (tmp_path / "LOGO.SVG").write_text("<svg/>")
    (tmp_path / "keep.py").write_text("x = 1\n")
    assert ingestable(tmp_path, None) == ("keep.py",)


def test_a_zero_byte_file_is_never_ingestable(tmp_path: Path) -> None:
    # 099's first half: py.typed is 0 bytes, split yields no section for it,
    # so diff reported it `new` on every run and bumped the batch counter.
    (tmp_path / "py.typed").write_text("")
    (tmp_path / "real.py").write_text("x = 1\n")
    assert ingestable(tmp_path, None) == ("real.py",)
