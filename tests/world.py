"""A built world, restored for each test instead of rebuilt.

Building a tree (clone a repo, ingest, embed, cluster, brief) costs a quarter
of a second; a module of thirty tests that each want the same built tree paid
it thirty times. The module builds once, copies the finished directory aside,
and each test gets a fresh copy of that copy at the same path, so every
absolute path the build recorded (the source's file URL, the cache clone's
remote) still points at the directory the test now owns.
"""

import shutil
from pathlib import Path


def snapshot(root: Path, into: Path) -> Path:
    """Copy a finished, closed world aside; return the copy's path."""
    copy = into / "snapshot"
    shutil.copytree(root, copy, symlinks=True)
    return copy


def restore(copy: Path, root: Path) -> Path:
    """Make ``root`` an exact, fresh copy of the snapshot; return it."""
    shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(copy, root, symlinks=True)
    return root
