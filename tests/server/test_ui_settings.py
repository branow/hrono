"""#199 (settings, edit half): config that can be changed from the page.

Every assertion is made against the REGISTRY the write lands in, not against
the page that reports it — a settings page that rendered a confirmation while
writing nothing, or that validated through its own rules instead of the
engine's, would look identical here otherwise.

The source these edits are made against is a REAL git repository (a bare one
in `tmp_path`), because `sources` writes run the real reach check on the way
in (`validation/git_validation.py`). A fake url would make every save here
prove the refusal path and nothing about the saving one, and it would go to the
network to do it.

The secret assertions use a real Fernet ciphertext written through the real
registry path: the trap this feature sets is a form that posts back the mask it
displayed, and only a real credential in the row can show it was not
overwritten.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from hrono.registry.write import MASK
from hrono.server.app import create_app
from hrono.summarize import briefs
from hrono.summarize.resolve import template_hash

KEY = Fernet.generate_key()
# Deliberately not vendor-shaped: what these tests need is a real Fernet
# ciphertext in the row, and a credential-looking literal trips secret scanners
# on every tool that reads this file.
TOKEN = "a-provider-token-that-must-survive-an-edit"


class Browser:
    def __init__(
        self,
        client: TestClient,
        tokens: dict,
        conn: object,
        repos: dict[str, Path],
    ) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn
        self.repos = repos
        self.cipher = Cipher.from_key(KEY, 1)

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def config(self) -> str:
        return self.client.get("/ui/config").text

    def save(self, collection: str, name: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/ui/config/{collection}/{name}/save", data=fields
        )

    def create(self, collection: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(f"/ui/config/{collection}/create", data=fields)

    def remove(self, collection: str, name: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/ui/config/{collection}/{name}/delete", data=fields
        )

    def shown(self, collection: str, name: str) -> str:
        """Exactly what the page put in that item's edit box.

        Posting THIS back is what a browser does, so the text under test is the
        one the page actually rendered rather than a copy of it written here,
        which would prove nothing about the page.
        """
        found = re.search(
            rf'<textarea class="code" id="edit-{collection}-{name}"'
            r"[^>]*>(.*?)</textarea>",
            self.config(),
            re.S,
        )
        assert found is not None, f"no edit box for {collection}/{name}"
        return html.unescape(found.group(1))

    def stored(self, collection: str, name: str) -> dict | None:
        row = registry_store.get(self.conn, collection, name)  # type: ignore[arg-type]
        return None if row is None else json.loads(row["config"])

    def plaintext(self, collection: str, name: str, *path: str) -> str:
        """A stored secret, decrypted the way the reader of it would."""
        row = registry_store.get(self.conn, collection, name)  # type: ignore[arg-type]
        value = json.loads(row["config"])  # type: ignore[index]
        for key in path:
            value = value[key]
        return self.cipher.decrypt(int(row["key_id"]), str(value))  # type: ignore[index]


def _bare_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "--bare", "--quiet", str(path)], check=True)
    return path


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    repos = {
        "origin": _bare_repo(tmp_path / "origin.git"),
        "moved": _bare_repo(tmp_path / "moved.git"),
        "docs": _bare_repo(tmp_path / "docs.git"),
    }
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    cipher = Cipher.from_key(KEY, record.key_id)
    # the seeder `hrono serve` itself runs (#021), not a planted is_default row
    seed_defaults(conn, cipher, COLLECTIONS)
    secret = cipher.encrypt(TOKEN)
    registry_store.insert(
        conn,
        "sources",
        "gh",
        json.dumps(
            {
                "name": "gh",
                "type": "git",
                "url": str(repos["origin"]),
                "auth": {"method": "token", "token": secret.ciphertext},
            }
        ),
        secret.key_id,
        "t",
    )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through; two threads on one sqlite connection interleave
        # transactions (#194).
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn, repos)
    conn.close()


def _source(name: str, url: Path) -> str:
    return json.dumps(
        {
            "name": name,
            "type": "git",
            "url": str(url),
            "auth": {"method": "none"},
        }
    )


def test_an_edit_lands_in_the_registry(browser: Browser) -> None:
    browser.sign_in()
    config = json.loads(browser.shown("sources", "gh"))
    config["url"] = str(browser.repos["moved"])

    answer = browser.save("sources", "gh", config=json.dumps(config))

    assert answer.status_code == 200  # followed the redirect
    assert browser.stored("sources", "gh")["url"] == str(  # type: ignore[index]
        browser.repos["moved"]
    )


def test_an_edit_does_not_write_the_mask_over_the_credential(
    browser: Browser,
) -> None:
    """The page can only ever show `***`, so the form posts `***` back.

    A save that took that literally would leave a config that looks exactly
    right and no longer authenticates — the failure nobody notices until the
    next sync.
    """
    browser.sign_in()
    shown = browser.shown("sources", "gh")
    assert json.loads(shown)["auth"]["token"] == MASK

    browser.save("sources", "gh", config=shown)

    assert browser.plaintext("sources", "gh", "auth", "token") == TOKEN
    assert browser.stored("sources", "gh")["auth"]["token"] != MASK  # type: ignore[index]


def test_a_replaced_secret_is_stored_encrypted(browser: Browser) -> None:
    """Typing over the mask must still REPLACE it, or the field is read-only."""
    browser.sign_in()
    replacement = "the-rotated-token"
    config = json.loads(browser.shown("sources", "gh"))
    config["auth"]["token"] = replacement

    browser.save("sources", "gh", config=json.dumps(config))

    assert browser.plaintext("sources", "gh", "auth", "token") == replacement
    assert replacement not in json.dumps(browser.stored("sources", "gh"))


def test_an_invalid_config_is_refused_with_the_field_named(
    browser: Browser,
) -> None:
    """The server already says which field and why; the page renders THAT."""
    browser.sign_in()

    answer = browser.save(
        "sources",
        "gh",
        config=json.dumps({"name": "gh", "type": "git"}),
    )

    assert "<code>git.url</code>" in answer.text
    assert "Field required" in answer.text
    assert browser.stored("sources", "gh")["url"] == str(  # type: ignore[index]
        browser.repos["origin"]
    )


def test_a_rejected_edit_keeps_what_was_typed(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.save("sources", "gh", config='{"name": "gh"')

    assert "not valid JSON" in answer.text
    assert "{&#34;name&#34;: &#34;gh&#34;" in answer.text


def test_a_hook_refusal_is_shown_as_its_own_reason(browser: Browser) -> None:
    """A validation HOOK is not a schema error and must not be flattened."""
    browser.sign_in()

    answer = browser.create(
        "trees",
        config=json.dumps({"name": "beta", "sources": ["nowhere"]}),
    )

    assert "tree names unregistered sources: nowhere" in answer.text
    assert browser.stored("trees", "beta") is None


def test_a_seeded_default_cannot_be_edited(browser: Browser) -> None:
    """Defaults are frozen: a forged post is refused, not merely undrawn."""
    browser.sign_in()
    before = browser.stored("prompts", "brief")
    assert before is not None

    answer = browser.save(
        "prompts",
        "brief",
        config=json.dumps({**before, "template": "rewritten {content}"}),
    )

    assert "a shipped default cannot be edited" in answer.text
    assert browser.stored("prompts", "brief") == before


def test_a_seeded_default_offers_no_edit_form(browser: Browser) -> None:
    browser.sign_in()

    page = browser.config()

    assert "/ui/config/prompts/brief/save" not in page
    assert "/ui/config/prompts/brief/delete" in page  # reset is offered


def test_a_default_is_reset_rather_than_removed(browser: Browser) -> None:
    browser.sign_in()
    shipped = browser.stored("prompts", "brief")
    assert shipped is not None
    registry_store.replace(
        browser.conn,  # type: ignore[arg-type]
        "prompts",
        "brief",
        json.dumps({**shipped, "template": "drifted {content}"}),
        None,
        "t",
    )

    browser.remove("prompts", "brief", confirm="1")

    assert browser.stored("prompts", "brief") == shipped


def test_a_delete_needs_the_box_ticked(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.remove("sources", "gh")

    assert "tick the box to confirm" in answer.text
    assert browser.stored("sources", "gh") is not None


def test_a_confirmed_delete_removes_the_row(browser: Browser) -> None:
    browser.sign_in()

    browser.remove("sources", "gh", confirm="1")

    assert browser.stored("sources", "gh") is None


def test_a_preview_writes_nothing_and_reports_the_blast_radius(
    browser: Browser,
) -> None:
    """`?dry_run=true`'s own answer (#190), before the edit is applied."""
    browser.sign_in()
    browser.create(
        "prompts",
        config=json.dumps(
            {"name": "mine", "role": "brief", "template": "Summarise {content}"}
        ),
    )

    answer = browser.save(
        "prompts",
        "mine",
        config=json.dumps(
            {"name": "mine", "role": "brief", "template": "Condense {content}"}
        ),
        preview="1",
    )

    assert "Nothing saved yet" in answer.text
    assert browser.stored("prompts", "mine")["template"] == (  # type: ignore[index]
        "Summarise {content}"
    )


def test_a_reader_sees_no_controls(browser: Browser) -> None:
    browser.sign_in("reader")

    page = browser.config()

    assert "/ui/config/sources/gh/save" not in page
    assert "/ui/config/sources/gh/delete" not in page
    assert "/ui/config/trees/new" not in page
    assert "/ui/config/sources/create" not in page


def test_a_readers_post_is_refused(browser: Browser) -> None:
    browser.sign_in("reader")

    answer = browser.save(
        "sources", "gh", config=_source("gh", browser.repos["moved"])
    )

    assert answer.status_code == 403
    assert browser.stored("sources", "gh")["url"] == str(  # type: ignore[index]
        browser.repos["origin"]
    )


def test_a_readers_delete_is_refused(browser: Browser) -> None:
    browser.sign_in("reader")

    answer = browser.remove("sources", "gh", confirm="1")

    assert answer.status_code == 403
    assert browser.stored("sources", "gh") is not None


def test_a_signed_out_post_is_refused(browser: Browser) -> None:
    answer = browser.client.post(
        "/ui/config/sources/gh/delete",
        data={"confirm": "1"},
        follow_redirects=False,
    )

    assert answer.status_code in (303, 401)
    assert browser.stored("sources", "gh") is not None


def test_a_write_redirects_so_a_refresh_repeats_nothing(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.client.post(
        "/ui/config/sources/create",
        data={"config": _source("docs", browser.repos["docs"])},
        follow_redirects=False,
    )

    assert answer.status_code == 303
    repeat = browser.client.get(answer.headers["location"])
    assert repeat.status_code == 200
    assert browser.stored("sources", "docs") is not None


def test_what_was_typed_cannot_break_out_of_the_textarea(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.create("sources", config="</textarea><script>alert(1)")

    assert "</textarea><script>alert(1)" not in answer.text
    assert "&lt;/textarea&gt;&lt;script&gt;" in answer.text


def test_a_tree_is_created_from_the_page(browser: Browser) -> None:
    """The gap the owner found: a tree could only be made from the CLI."""
    browser.sign_in()

    answer = browser.client.post(
        "/ui/config/trees/new", data={"name": "beta", "sources": ["gh"]}
    )

    assert answer.status_code == 200  # followed the redirect
    assert browser.stored("trees", "beta") == {
        "name": "beta",
        "sources": ["gh"],
    }


def test_the_picker_offers_the_sources_that_are_registered(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.config()

    assert '<input type="checkbox" name="sources" value="gh">' in page


def test_every_ticked_source_reaches_the_tree(browser: Browser) -> None:
    """A picker posts its name once per tick; the first is not the set."""
    browser.sign_in()
    browser.create("sources", config=_source("docs", browser.repos["docs"]))

    browser.client.post(
        "/ui/config/trees/new",
        data={"name": "beta", "sources": ["gh", "docs"]},
    )

    assert browser.stored("trees", "beta")["sources"] == ["gh", "docs"]  # type: ignore[index]


def test_a_tree_with_no_source_is_refused_against_the_field(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.client.post("/ui/config/trees/new", data={"name": "beta"})

    assert "<code>sources</code>" in answer.text
    assert "at least 1 item" in answer.text
    assert browser.stored("trees", "beta") is None


def test_a_new_tree_appears_in_the_switcher(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.client.post(
        "/ui/config/trees/new", data={"name": "beta", "sources": ["gh"]}
    )

    assert "/ui/config?tree=beta" in answer.text


def test_the_delete_warning_is_shown_before_the_deletion(
    browser: Browser,
) -> None:
    """`before_delete` says what removing a tree's config ARMS (#167).

    An operator has to read that beside the button, not in the receipt — by
    then the next maintain is already unscoped.
    """
    browser.sign_in()
    browser.client.post(
        "/ui/config/trees/new", data={"name": "beta", "sources": ["gh"]}
    )
    _a_topic_in(browser, "beta")

    page = browser.config()

    assert "tree beta now maps EVERY source" in page
    assert browser.stored("trees", "beta") is not None


def _a_topic_in(browser: Browser, tree: str) -> int:
    """One built topic, made the way the pipeline makes one."""
    conn = browser.conn
    with conn:  # type: ignore[attr-defined]
        body = b"a chunk of the corpus\n"
        digest = content_hash(body)
        istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
        section = istore.insert_section(
            conn,  # type: ignore[arg-type]
            source="gh",
            address=Address("git", "x/y", "a.md", "v1"),
            start=0,
            end=len(body),
            content_hash=digest,
            ordinal=0,
        )
        return cluster_store.add_leaf_node(  # type: ignore[no-any-return]
            conn,  # type: ignore[arg-type]
            tree,
            [(section, False, None)],
        )


def _brief_written_by(
    browser: Browser, node: int, prompt: str, template: str
) -> None:
    """A brief carrying its own provenance — which is what goes stale (#064)."""
    conn = browser.conn
    with conn:  # type: ignore[attr-defined]
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            node,
            "What this topic says.",
            model_name="writer",
            prompt_name=prompt,
            prompt_hash=template_hash(template),
            member_signature=briefs.member_signature(conn, node),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
        )


def test_a_preview_names_the_trees_an_edit_would_restale(
    browser: Browser,
) -> None:
    """The blast radius itself, not only the "nothing saved" half.

    The empty answer and the populated one are different markup; a preview
    that could only ever render "no tree is affected" would pass a test that
    never built a brief for it to invalidate.
    """
    browser.sign_in()
    browser.create(
        "prompts",
        config=json.dumps(
            {"name": "mine", "role": "brief", "template": "Summarise {content}"}
        ),
    )
    node = _a_topic_in(browser, "default")
    _brief_written_by(browser, node, "mine", "Summarise {content}")

    answer = browser.save(
        "prompts",
        "mine",
        config=json.dumps(
            {"name": "mine", "role": "brief", "template": "Condense {content}"}
        ),
        preview="1",
    )

    assert "1 topic to rewrite at level 0" in answer.text
    assert "the next run would rewrite them" in answer.text
    assert browser.stored("prompts", "mine")["template"] == (  # type: ignore[index]
        "Summarise {content}"
    )
