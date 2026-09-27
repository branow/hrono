"""#190 (T58, impact half): what a shared-resource edit would do.

The claim under test is not "a number appears" but that the number is the one
the next run would act on. So the prompt case is asserted against
`briefs.stale_or_missing` — the SAME function the `brief` op selects with —
and the cases where nothing goes stale are asserted as saying so, because a
preview that reassures wrongly is worse than no preview.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import pins
from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import connection_validation, impact, model_validation
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import briefs
from hrono.summarize.resolve import template_hash

KEY = Fernet.generate_key()
MODEL = "sonnet"
TEMPLATE = "Brief this group: {content}"


class Api:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn
        self.nodes: dict[str, list[int]] = {}
        self.urls: dict[str, str] = {}

    def head(self, role: str = "writer") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def dry_run(self, collection: str, name: str, body: dict, role="writer"):  # type: ignore[no-untyped-def]
        return self.client.put(
            f"/{collection}/{name}?dry_run=true",
            json=body,
            headers=self.head(role),
        )

    def stored(self, collection: str, name: str) -> dict:
        row = registry_store.get(self.conn, collection, name)  # type: ignore[arg-type]
        return json.loads(row["config"])


def _section(conn: object, source: str, path: str) -> int:
    body = f"{source}/{path}\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source=source,
        address=Address("git", f"ex/{source}", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


def _brief(conn: object, node: int, prompt_hash: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node,
        f"A summary of {node}.",
        model_name=MODEL,
        prompt_name="brief",
        prompt_hash=prompt_hash,
        member_signature=briefs.member_signature(conn, node),  # type: ignore[arg-type]
        input_tokens=1,
        output_tokens=1,
    )


@pytest.fixture(autouse=True)
def _offline_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider credential checks stay offline, as `test_connections.py` does.

    The git sources below are REAL local repositories — the reachability check
    that runs on every source write is a real one here, because "an auth-only
    edit changes nothing" is a claim about a source the engine accepted.
    """
    for name in ("_get", "_bearer_get"):
        monkeypatch.setattr(
            connection_validation, name, lambda url, key, timeout: 200
        )
    monkeypatch.setattr(
        model_validation,
        "_default_generate",
        lambda config, connection, timeout: "ok",
    )


def _repo(at: Path) -> str:
    at.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", "--bare", str(at)], check=True)
    return str(at)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    """Two trees over two sources, each with briefed leaves.

    Two on purpose: "tree-keyed impact" is a claim that the answer differs per
    tree, and one tree cannot tell a per-tree answer from a global one (#054).
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    for name, config in (
        (
            "docs",
            {
                "name": "docs",
                "type": "git",
                "url": _repo(tmp_path / "d"),
                "auth": {"method": "none"},
            },
        ),
        (
            "code",
            {
                "name": "code",
                "type": "git",
                "url": _repo(tmp_path / "c"),
                "auth": {"method": "none"},
            },
        ),
    ):
        registry_store.insert(
            conn, "sources", name, json.dumps(config), None, "t"
        )
    registry_store.insert(
        conn,
        "prompts",
        "brief",
        json.dumps({"name": "brief", "role": "brief", "template": TEMPLATE}),
        None,
        "t",
    )
    registry_store.insert(
        conn,
        "models",
        MODEL,
        json.dumps(
            {
                "name": MODEL,
                "kind": "text",
                "connection": "anthropic",
                "model": "claude-sonnet",
                "role": "brief",
            }
        ),
        None,
        "t",
    )
    registry_store.insert(
        conn,
        "connections",
        "anthropic",
        json.dumps(
            {
                "name": "anthropic",
                "provider": "anthropic",
                "auth": {"method": "api-key", "key": "not-a-key-" + "x" * 8},
            }
        ),
        None,
        "t",
    )
    nodes: dict[str, list[int]] = {}
    with conn:
        for tree, source in (("alpha", "docs"), ("beta", "code")):
            registry_store.insert(
                conn,
                "trees",
                tree,
                json.dumps({"name": tree, "sources": [source]}),
                None,
                "t",
            )
            made = [
                cluster_store.add_leaf_node(
                    conn,
                    tree,
                    [(_section(conn, source, f"{i}.md"), False, None)],
                )
                for i in range(2)
            ]
            for node in made:
                _brief(conn, node, template_hash(TEMPLATE))
            nodes[tree] = made
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        api = Api(client, tokens, conn)
        api.nodes = nodes
        api.urls = {
            "docs": str(tmp_path / "d"),
            "code": str(tmp_path / "c"),
            "moved": _repo(tmp_path / "moved"),
        }
        yield api
    conn.close()


def _by_tree(answer: object) -> dict[str, dict]:
    return {
        row["tree"]: row
        for row in answer.json()["affected_trees"]  # type: ignore[attr-defined]
    }


def test_a_dry_run_writes_nothing(api: Api) -> None:
    api.dry_run(
        "prompts",
        "brief",
        {
            "name": "brief",
            "role": "brief",
            "template": "Totally new: {content}",
        },
    )

    assert api.stored("prompts", "brief")["template"] == TEMPLATE


def test_a_prompt_edit_counts_the_briefs_it_would_rewrite(api: Api) -> None:
    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    impact = _by_tree(answer)
    assert impact["alpha"]["stale"]["nodes"] == 2
    assert impact["beta"]["stale"]["nodes"] == 2
    assert impact["alpha"]["ops"] == ["brief"]
    assert impact["alpha"]["stale"]["levels"] == [0]


def test_a_brief_already_stale_is_not_this_edits_blast_radius(
    api: Api,
) -> None:
    """The question is what THIS edit changes, not what is already waiting."""
    with api.conn:  # type: ignore[union-attr]
        briefs.mark_stale(api.conn, api.nodes["alpha"][0])  # type: ignore[arg-type]

    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    assert _by_tree(answer)["alpha"]["stale"]["nodes"] == 1


def test_a_pinned_brief_is_not_counted(api: Api) -> None:
    """The pin holds whatever the prompt says (#154), so no work is coming."""
    with api.conn:  # type: ignore[union-attr]
        pins.pin(api.conn, pins.BRIEF, api.nodes["beta"][0], reason="held")  # type: ignore[arg-type]

    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    assert _by_tree(answer)["beta"]["stale"]["nodes"] == 1


def test_an_unchanged_prompt_affects_nothing(api: Api) -> None:
    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": TEMPLATE},
    )

    assert answer.json()["affected_trees"] == []


def test_an_auth_only_source_edit_changes_no_bytes(api: Api) -> None:
    """`implementation-notes.md`: auth-only edit = no staleness, same bytes.

    Asked of `preview` directly rather than over HTTP: rotating a credential on
    a LOCAL repository is not a reachable git remote, and the write-time
    reachability check would refuse it before the rule under test is reached.
    Faking that check to get a preview out of it would be testing the fake.
    """
    proposed = {
        "name": "docs",
        "type": "git",
        "url": api.urls["docs"],
        "auth": {"method": "token", "token": "a-rotated-credential"},
    }

    assert impact.preview(api.conn, "sources", "docs", proposed) == ()  # type: ignore[arg-type]


def test_the_same_edit_with_a_new_url_is_not_auth_only(api: Api) -> None:
    # the control: the rule is about WHICH field moved, and a test that only
    # ever sees "nothing happened" cannot tell that from a broken preview
    proposed = {
        "name": "docs",
        "type": "git",
        "url": api.urls["moved"],
        "auth": {"method": "token", "token": "a-rotated-credential"},
    }

    assert impact.preview(api.conn, "sources", "docs", proposed) != ()  # type: ignore[arg-type]


def test_a_url_edit_reaches_only_the_trees_that_pull_it(api: Api) -> None:
    """#054: a tree's sources are its own, and alpha does not read code."""
    answer = api.dry_run(
        "sources",
        "docs",
        {
            "name": "docs",
            "type": "git",
            "url": api.urls["moved"],
            "auth": {"method": "none"},
        },
    )

    impact = _by_tree(answer)
    assert set(impact) == {"alpha"}
    assert impact["alpha"]["ops"] == ["sync", "cluster", "brief"]


def test_an_unmeasurable_count_is_null_and_says_why(api: Api) -> None:
    """How many sections a new url yields is not knowable without syncing."""
    answer = api.dry_run(
        "sources",
        "docs",
        {
            "name": "docs",
            "type": "git",
            "url": api.urls["moved"],
            "auth": {"method": "none"},
        },
    )

    alpha = _by_tree(answer)["alpha"]
    assert alpha["stale"]["sections"] is None
    assert "not knowable without doing it" in alpha["reason"]
    assert alpha["stale"]["nodes"] == 2  # the topics holding its chunks


def test_repointing_a_model_says_nothing_goes_stale(api: Api) -> None:
    """The gap an operator must not discover after clicking.

    `_is_fresh` compares the model NAME, so swapping the upstream model leaves
    every brief looking fresh. Saying "0 nodes" without saying why would read
    as "this is safe".
    """
    answer = api.dry_run(
        "models",
        MODEL,
        {
            "name": MODEL,
            "kind": "text",
            "connection": "anthropic",
            "model": "claude-opus",
            "role": "brief",
        },
    )

    impact = _by_tree(answer)
    assert impact["alpha"]["stale"]["nodes"] == 0
    assert "records the model NAME" in impact["alpha"]["reason"]
    assert impact["alpha"]["ops"] == []


def test_a_connection_edit_names_what_rides_on_it(api: Api) -> None:
    answer = api.dry_run(
        "connections",
        "anthropic",
        {
            "name": "anthropic",
            "provider": "anthropic",
            "auth": {"method": "api-key", "key": "rotated-" + "y" * 8},
        },
    )

    rows = answer.json()["affected_trees"]
    assert len(rows) == 1
    assert MODEL in rows[0]["reason"]
    assert rows[0]["stale"]["nodes"] == 0


def test_an_invalid_body_is_a_validation_error_in_dry_run_too(
    api: Api,
) -> None:
    # a preview of an edit that would be rejected is a rejection
    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "no placeholder here"},
    )

    assert answer.status_code >= 400


def test_a_dry_run_needs_the_write_role(api: Api) -> None:
    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
        role="reader",
    )

    assert answer.status_code == 403


def _upper(api: Api, tree: str) -> int:
    """Put a briefed level above a tree's leaves."""
    with api.conn:  # type: ignore[union-attr]
        api.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (tree,),
        )
        node = int(
            api.conn.execute(  # type: ignore[attr-defined]
                "SELECT MAX(id) FROM nodes"
            ).fetchone()[0]
        )
        for leaf in api.nodes[tree]:
            cluster_store.add_child(
                api.conn, node, leaf, attached=False, similarity=None
            )
        briefs.upsert(
            api.conn,  # type: ignore[arg-type]
            node,
            "A summary of summaries.",
            model_name=MODEL,
            prompt_name="brief-upper",
            prompt_hash=template_hash(UPPER_TEMPLATE),
            member_signature=briefs.member_signature(api.conn, node),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
        )
    return node


UPPER_TEMPLATE = "Brief these briefs: {content}"


def test_a_leaf_prompt_edit_leaves_the_upper_level_alone(api: Api) -> None:
    """The roles govern different levels, and the preview has to know which.

    `brief` writes level 0 and `brief-upper` every level above it. A preview
    that counted both would tell an operator to expect twice the work, from
    an edit that cannot cause it.
    """
    _upper(api, "alpha")

    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    assert _by_tree(answer)["alpha"]["stale"]["levels"] == [0]
    assert _by_tree(answer)["alpha"]["stale"]["nodes"] == 2


def test_an_upper_prompt_edit_reaches_only_the_upper_levels(
    api: Api,
) -> None:
    api.conn.execute("SELECT 1")  # type: ignore[attr-defined]
    _upper(api, "alpha")
    with api.conn:  # type: ignore[union-attr]
        registry_store.insert(
            api.conn,  # type: ignore[arg-type]
            "prompts",
            "brief-upper",
            json.dumps(
                {
                    "name": "brief-upper",
                    "role": "brief-upper",
                    "template": UPPER_TEMPLATE,
                }
            ),
            None,
            "t",
        )

    answer = api.dry_run(
        "prompts",
        "brief-upper",
        {
            "name": "brief-upper",
            "role": "brief-upper",
            "template": "Rather differently: {content}",
        },
    )

    alpha = _by_tree(answer)["alpha"]
    assert alpha["stale"]["levels"] == [1]
    assert alpha["stale"]["nodes"] == 1
    assert alpha["ops"] == ["brief-upper"]


def test_a_tree_with_no_briefs_yet_gains_nothing_from_an_edit(
    api: Api,
) -> None:
    """Its briefs are missing, so the next run rewrites them either way."""
    with api.conn:  # type: ignore[union-attr]
        api.conn.execute(  # type: ignore[attr-defined]
            "DELETE FROM briefs WHERE node_id IN (?, ?)",
            tuple(api.nodes["beta"]),
        )

    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    assert "beta" not in _by_tree(answer)


def test_the_roles_are_told_apart_by_role_not_by_their_text(
    api: Api,
) -> None:
    """Two prompts may hold the same words, and still govern different levels.

    Nothing stops an install from wording `brief` and `brief-upper` alike. If
    the preview told them apart by template hash alone, an edit to one would
    be reported as work at the other's level — which is the wrong number in
    the reassuring direction for `brief-upper` and the alarming one for
    `brief`.
    """
    node = _upper(api, "alpha")
    with api.conn:  # type: ignore[union-attr]
        briefs.upsert(
            api.conn,  # type: ignore[arg-type]
            node,
            "A summary of summaries.",
            model_name=MODEL,
            prompt_name="brief-upper",
            prompt_hash=template_hash(TEMPLATE),  # the SAME words
            member_signature=briefs.member_signature(api.conn, node),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
        )

    answer = api.dry_run(
        "prompts",
        "brief",
        {"name": "brief", "role": "brief", "template": "Different: {content}"},
    )

    alpha = _by_tree(answer)["alpha"]
    assert alpha["stale"]["levels"] == [0]
    assert alpha["stale"]["nodes"] == 2  # the two leaves, not the topic above
