"""Reference labels for scoring: a file's component and its kind.

They are used to SCORE a clustering, never to build one. Both come from
path rules, written as data and walked by one function each.

- Component: the nearest folder that holds a build file (a deployable unit
  such as `sbc-pay/pay-api` or `lear/queue_services/entity-filer`). Build
  files inside dev-container or test folders do not count. A file with no
  such folder belongs to the repository when its root has a build file,
  and to its repository's top-level folder otherwise.
- Kind: the first rule whose pattern matches the path.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

BUILD_FILES = ("pyproject.toml", "setup.py", "package.json", "Dockerfile")
NOT_COMPONENT_ROOTS = re.compile(r"(^|/)(\.devcontainer|tests?|e2e)(/|$)")

KIND_RULES: tuple[tuple[str, str], ...] = (
    ("migration", r"(^|/)(migrations|alembic)/"),
    (
        "test",
        r"(^|/)(tests?|__tests__|e2e|spec)/"
        r"|(^|/)(test_[^/]*|[^/]*_test\.py|conftest\.py|[^/]*\.(spec|test)\.[jt]s)$",
    ),
    ("fixture", r"(^|/)(fixtures|mocks?|__mocks__|testdata|data)/"),
    (
        "build",
        r"(^|/)(\.github|\.devcontainer|devops|openshift|helm|k8s)/"
        r"|(^|/)(Dockerfile[^/]*|Makefile|docker-compose[^/]*|"
        r"requirements[^/]*\.txt|setup\.(py|cfg)|pyproject\.toml|"
        r"package(-lock)?\.json|tox\.ini|\.[^/]*rc|[^/]*\.(cfg|ini|toml)|"
        r"\.env[^/]*|\.gitignore|\.dockerignore|\.editorconfig|"
        r"(tsconfig|jest\.config|vite\.config|vue\.config|babel\.config)"
        r"[^/]*)$",
    ),
    ("docs", r"(^|/)(docs?)/|\.(md|rst|txt|html)$"),
)
_COMPILED = tuple((kind, re.compile(pattern)) for kind, pattern in KIND_RULES)


def kind_of(path: str) -> str:
    for kind, pattern in _COMPILED:
        if pattern.search(path):
            return kind
    return "code"


def component_of(source: str, path: str, tracked: frozenset[str]) -> str:
    folder = PurePosixPath(path).parent
    while str(folder) != ".":
        text = str(folder)
        if not NOT_COMPONENT_ROOTS.search(text) and any(
            f"{text}/{name}" in tracked for name in BUILD_FILES
        ):
            return f"{source}/{text}"
        folder = folder.parent
    if any(name in tracked for name in BUILD_FILES):
        return source
    top = PurePosixPath(path).parts
    return f"{source}/{top[0]}" if len(top) > 1 else f"{source}/(root)"
