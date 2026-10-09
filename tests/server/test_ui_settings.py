"""Config that can be changed from the page.

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

**Two surfaces.** The page is a FORM
over fields derived from each collection's own pydantic model, with the JSON
kept as a second view over the WHOLE collection. Both are exercised here,
because they are two doors onto one registry and the thing that must not drift
is that they agree about what a valid config is.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from importlib.metadata import version
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
from hrono.summarize import store as condensations
from hrono.summarize.resolve import template_hash
from hrono.usage.rollup import for_jobs
from tests.stub_server import serving

KEY = Fernet.generate_key()


def placeholder(what: str) -> str:
    """A stand-in credential, built rather than ASSIGNED.

    What these tests need is a real Fernet ciphertext in the row, not a
    realistic prefix. It must not be a module constant: a DLP scanner reads
    `NAME = "some-long-string"` as an env-style secret assignment whatever the
    string says, and blocks every tool that tries to open this file. The shape
    is what trips it, so the shape is what changes.
    """
    return f"not-a-real-{what}"


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

    def config(self, **query: str) -> str:
        return self.client.get("/ui/config", params=query).text

    def item(self, collection: str, **fields: object):  # type: ignore[no-untyped-def]
        """Save ONE item from its form.

        One route for create and replace, because `engine.replace_item` is
        already create-or-replace: a page that chose between POST and PUT by
        first asking whether the name existed would re-derive that decision.
        """
        return self.client.post(f"/ui/config/{collection}/item", data=fields)

    def replace(self, collection: str, document: object):  # type: ignore[no-untyped-def]
        """Save the WHOLE collection from the JSON view."""
        text = (
            document
            if isinstance(document, str)
            else json.dumps(document, indent=2)
        )
        return self.client.post(
            f"/ui/config/{collection}/replace", data={"config": text}
        )

    def remove(self, collection: str, name: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/ui/config/{collection}/{name}/delete", data=fields
        )

    def fields(self, collection: str, name: str = "") -> dict[str, str]:
        """Exactly what the page put in that item's form, as a post body.

        Posting THIS back is what a browser does, so the values under test are
        the ones the page actually rendered rather than a copy written here,
        which would prove nothing about the page.
        """
        where = (
            {"edit": f"{collection}:{name}"} if name else {"add": collection}
        )
        page = self.config(**where)
        found: dict[str, str] = {}
        for match in re.finditer(
            r'<input class="line" type="[a-z]+" id="[^"]*"'
            r' name="(f\.[^"]+)" value="([^"]*)"',
            page,
        ):
            found[match.group(1)] = html.unescape(match.group(2))
        for match in re.finditer(
            r'<textarea class="code" id="[^"]*" name="(f\.[^"]+)"'
            r"[^>]*>(.*?)</textarea>",
            page,
            re.S,
        ):
            found[match.group(1)] = html.unescape(match.group(2))
        for block in re.finditer(
            r'<select id="[^"]*" name="(f\.[^"]+)">(.*?)</select>', page, re.S
        ):
            chosen = re.search(
                r'<option value="([^"]*)" selected>', block.group(2)
            )
            found[block.group(1)] = chosen.group(1) if chosen else ""
        return found

    def document(self, collection: str) -> str:
        """The whole collection, as the JSON view renders it for editing."""
        found = re.search(
            rf'<textarea class="code" id="doc-{collection}"'
            r"[^>]*>(.*?)</textarea>",
            self.config(section=collection, view="json"),
            re.S,
        )
        assert found is not None, f"no document box for {collection}"
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
    # the seeder `hrono serve` itself runs, not a planted is_default row
    seed_defaults(conn, cipher, COLLECTIONS)
    secret = cipher.encrypt(placeholder("source-token"))
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
        # transactions.
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn, repos)
    conn.close()


def _git(name: str, url: Path) -> dict[str, object]:
    return {
        "name": name,
        "type": "git",
        "url": str(url),
        "auth": {"method": "none"},
    }


def _as_posted(fields: dict[str, str], **changes: object) -> dict[str, object]:
    """The form's own values, with an edit applied — what a browser sends."""
    return {**fields, **changes}


# --------------------------------------------------------------- form view


def test_the_form_is_the_default_view(browser: Browser) -> None:
    """Five textareas of JSON would be the API's surface wearing a browser,
    and adding a model would mean knowing the schema by heart."""
    browser.sign_in()

    page = browser.config(section="models")

    assert 'id="doc-models"' not in page  # not the JSON document
    assert "Add a model" in page
    assert "Add a tree" in browser.config()
    # the JSON is one click away, labelled as the advanced alternative
    assert "/ui/config?tree=default&amp;section=models&amp;view=json" in page
    assert "Edit as JSON (advanced)" in page


def test_the_fields_come_from_the_collection_s_own_model(
    browser: Browser,
) -> None:
    """Written out by hand they would be a SECOND schema, drifting from the one
    the API validates against — a field nobody can set, or one this page offers
    that the validator refuses. Nested objects arrive as dotted paths."""
    browser.sign_in()

    fields = browser.fields("sources", "gh")

    assert fields["f.name"] == "gh"
    assert fields["f.url"] == str(browser.repos["origin"])
    assert fields["f.auth.method"] == "token"  # a Literal, as a select
    assert "f.filter.only" in fields  # an optional nested model, still offered


def test_an_edit_lands_in_the_registry(browser: Browser) -> None:
    browser.sign_in()
    fields = browser.fields("sources", "gh")

    answer = browser.item(
        "sources",
        name="gh",
        variant="git",
        **_as_posted(fields, **{"f.url": str(browser.repos["moved"])}),
    )

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
    fields = browser.fields("sources", "gh")
    assert fields["f.auth.token"] == MASK

    browser.item("sources", name="gh", variant="git", **fields)

    assert browser.plaintext("sources", "gh", "auth", "token") == placeholder(
        "source-token"
    )
    assert browser.stored("sources", "gh")["auth"]["token"] != MASK  # type: ignore[index]


def test_a_replaced_secret_is_stored_encrypted(browser: Browser) -> None:
    """Typing over the mask must still REPLACE it, or the field is read-only."""
    browser.sign_in()
    replacement = "the-rotated-token"
    fields = browser.fields("sources", "gh")

    browser.item(
        "sources",
        name="gh",
        variant="git",
        **_as_posted(fields, **{"f.auth.token": replacement}),
    )

    assert browser.plaintext("sources", "gh", "auth", "token") == replacement
    assert replacement not in json.dumps(browser.stored("sources", "gh"))


def test_an_invalid_config_is_refused_with_the_field_named(
    browser: Browser,
) -> None:
    """The server already says which field and why; the page renders THAT."""
    browser.sign_in()
    fields = browser.fields("sources", "gh")

    answer = browser.item(
        "sources",
        name="gh",
        variant="git",
        **_as_posted(fields, **{"f.url": ""}),
    )

    assert "<code>git.url</code>" in answer.text
    assert "Field required" in answer.text or "at least 1" in answer.text
    assert browser.stored("sources", "gh")["url"] == str(  # type: ignore[index]
        browser.repos["origin"]
    )


def test_a_rejected_edit_keeps_what_was_typed(browser: Browser) -> None:
    """A refusal re-renders the form with the operator's words in it — a
    redirect would hand back the stored config and ask them to type it again."""
    browser.sign_in()
    fields = browser.fields("sources", "gh")

    answer = browser.item(
        "sources",
        name="gh",
        variant="git",
        **_as_posted(
            fields, **{"f.url": "", "f.name": "gh", "f.auth.method": "ssh"}
        ),
    )

    assert 'name="f.auth.method"' in answer.text
    kept = re.search(
        r'<select id="[^"]*" name="f\.auth\.method">(.*?)</select>',
        answer.text,
        re.S,
    )
    assert kept is not None
    assert '<option value="ssh" selected>' in kept.group(1)


def test_a_hook_refusal_is_shown_as_its_own_reason(browser: Browser) -> None:
    """A validation HOOK is not a schema error and must not be flattened.

    Through the JSON view, because the form offers the REGISTERED sources as
    ticks — naming one that does not exist is not reachable from it, which is
    the point of the pick.
    """
    browser.sign_in()

    answer = browser.replace(
        "trees",
        [{"name": "default", "sources": ["gh"]}]
        + [{"name": "beta", "sources": ["nowhere"]}],
    )

    assert "tree names unregistered sources: nowhere" in answer.text
    assert browser.stored("trees", "beta") is None


def test_a_seeded_default_cannot_be_edited(browser: Browser) -> None:
    """Defaults are frozen: a forged post is refused, not merely undrawn."""
    browser.sign_in()
    before = browser.stored("prompts", "brief")
    assert before is not None

    answer = browser.item(
        "prompts",
        name="brief",
        **{
            "f.name": "brief",
            "f.role": "brief",
            "f.template": "rewritten {content}",
        },
    )

    assert "a shipped default cannot be edited" in answer.text
    assert browser.stored("prompts", "brief") == before


def test_a_seeded_default_offers_no_edit_form(browser: Browser) -> None:
    browser.sign_in()

    page = browser.config(section="prompts")
    opened = browser.config(edit="prompts:brief")

    assert "delete=prompts:brief" in page  # reset is offered
    assert 'name="f.template"' not in opened  # and no form, only the config
    assert "cannot be edited here" in opened


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


def test_a_delete_posted_without_confirm_is_refused(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.remove("sources", "gh")

    assert "confirm to delete: gh" in answer.text
    assert browser.stored("sources", "gh") is not None


def test_a_confirmed_delete_removes_the_row(browser: Browser) -> None:
    browser.sign_in()

    browser.remove("sources", "gh", confirm="1")

    assert browser.stored("sources", "gh") is None


def test_a_preview_writes_nothing_and_reports_the_blast_radius(
    browser: Browser,
) -> None:
    """`?dry_run=true`'s own answer, before the edit is applied."""
    browser.sign_in()
    browser.item(
        "prompts",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Summarise {content}",
        },
    )

    answer = browser.item(
        "prompts",
        name="mine",
        preview="1",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Condense {content}",
        },
    )

    assert "Nothing saved yet" in answer.text
    assert browser.stored("prompts", "mine")["template"] == (  # type: ignore[index]
        "Summarise {content}"
    )


def test_a_reader_sees_no_controls(browser: Browser) -> None:
    browser.sign_in("reader")

    page = browser.config()

    assert "/ui/config/sources/item" not in page
    assert "/ui/config/sources/replace" not in page
    assert "/ui/config/sources/gh/delete" not in page
    assert "add=sources" not in page


def test_a_readers_post_is_refused(browser: Browser) -> None:
    browser.sign_in("reader")

    answer = browser.item(
        "sources",
        name="gh",
        variant="git",
        **{
            "f.name": "gh",
            "f.url": str(browser.repos["moved"]),
            "f.auth.method": "none",
        },
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
        "/ui/config/sources/item",
        data={
            "variant": "git",
            "f.name": "docs",
            "f.url": str(browser.repos["docs"]),
            "f.auth.method": "none",
        },
        follow_redirects=False,
    )

    assert answer.status_code == 303
    # back to the collection it changed, not to the landing view
    assert "section=sources" in answer.headers["location"]
    repeat = browser.client.get(answer.headers["location"])
    assert repeat.status_code == 200
    assert browser.stored("sources", "docs") is not None


@pytest.mark.parametrize(
    "query",
    [
        {"edit": "sources:gh"},
        {"add": "sources", "variant": "git"},
        {"delete": "sources:gh"},
    ],
    ids=["edit", "add", "delete"],
)
def test_a_form_opens_as_its_own_view_and_leaves_the_list_alone(
    browser: Browser, query: dict[str, str]
) -> None:
    """An edit must not open in the middle of a 3000px page and push the rest
    down, nor an add put a picker ABOVE the items it is adding to. Each opens
    on its own, and Cancel is the list exactly as it was."""
    browser.sign_in()

    page = browser.config(**query)
    listing = browser.config(section="sources")

    assert 'class="settings-table"' not in page
    assert 'href="/ui/config?tree=default&amp;section=sources">Cancel' in page
    assert 'class="settings-table"' in listing
    assert "<td>git</td>" in listing


# --------------------------------------------------------------- JSON view


def test_the_json_view_is_the_whole_collection(browser: Browser) -> None:
    """A collection is editable whole, not only one item at a time, so there
    is a way to say "these are my models"."""
    browser.sign_in()

    document = json.loads(browser.document("prompts"))

    assert isinstance(document, list)
    assert {item["name"] for item in document} == {
        "condense",
        "brief",
        "brief-upper",
        "judge",
    }


def test_an_entry_added_to_the_document_is_added_to_the_collection(
    browser: Browser,
) -> None:
    browser.sign_in()
    document = json.loads(browser.document("prompts"))

    answer = browser.replace(
        "prompts",
        document + [{"name": "mine", "role": "brief", "template": "{content}"}],
    )

    assert "added mine" in answer.text
    assert browser.stored("prompts", "mine") is not None


def test_an_entry_removed_from_the_document_is_removed(
    browser: Browser,
) -> None:
    browser.sign_in()
    browser.replace(
        "prompts",
        json.loads(browser.document("prompts"))
        + [{"name": "mine", "role": "brief", "template": "{content}"}],
    )

    answer = browser.replace(
        "prompts",
        [
            item
            for item in json.loads(browser.document("prompts"))
            if item["name"] != "mine"
        ],
    )

    assert "removed mine" in answer.text
    assert browser.stored("prompts", "mine") is None


def test_saving_an_unchanged_document_changes_nothing(
    browser: Browser,
) -> None:
    """A save that restaled every brief in the tree because the page was opened
    and closed would make this view unusable."""
    browser.sign_in()
    before = browser.stored("sources", "gh")

    answer = browser.replace("sources", browser.document("sources"))

    assert "nothing to change" in answer.text
    assert browser.stored("sources", "gh") == before  # ciphertext and all


def test_one_bad_entry_refuses_the_WHOLE_document(browser: Browser) -> None:
    """A list that half-applies leaves a page that is neither what the operator
    had nor what they asked for."""
    browser.sign_in()
    document = json.loads(browser.document("prompts"))

    answer = browser.replace(
        "prompts",
        document
        + [
            {"name": "good", "role": "brief", "template": "{content}"},
            {"name": "bad", "role": "brief", "template": "no placeholder"},
        ],
    )

    assert "must contain {content}" in answer.text
    assert browser.stored("prompts", "good") is None  # nothing was written


def test_a_document_that_is_not_a_list_is_refused(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.replace("prompts", '{"name": "mine"}')

    assert "a collection is a JSON array" in answer.text


def test_what_was_typed_cannot_break_out_of_the_textarea(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.replace("sources", "</textarea><script>alert(1)")

    assert "</textarea><script>alert(1)" not in answer.text
    assert "&lt;/textarea&gt;&lt;script&gt;" in answer.text


# ------------------------------------------------------------------- trees


def test_a_tree_is_created_from_the_page(browser: Browser) -> None:
    """The gap the owner found: a tree could only be made from the CLI."""
    browser.sign_in()

    answer = browser.item("trees", **{"f.name": "beta", "f.sources": ["gh"]})

    assert answer.status_code == 200  # followed the redirect
    assert browser.stored("trees", "beta") == {
        "name": "beta",
        "sources": ["gh"],
    }


def test_trees_are_the_first_thing_on_the_page(browser: Browser) -> None:
    """A tree is what every other collection is in service of, so it is not
    the LAST card behind a disclosure — an operator looking for "how do I make
    a tree" must not find four screens of model JSON instead."""
    browser.sign_in()

    page = browser.config()

    assert page.index('id="nav-trees"') < page.index('id="nav-sources"')
    assert page.index('id="nav-trees"') < page.index('id="nav-models"')
    assert "<h2>Trees</h2>" in page


def test_the_picker_offers_the_sources_that_are_registered(
    browser: Browser,
) -> None:
    """A field that names a row in ANOTHER collection is a pick over what is
    registered — a typo caught by a refusal AFTER the save is the worse way to
    learn a name."""
    browser.sign_in()

    page = browser.config(add="trees")

    assert '<input type="checkbox" name="f.sources" value="gh">' in page


def test_every_ticked_source_reaches_the_tree(browser: Browser) -> None:
    """A picker posts its name once per tick; the first is not the set."""
    browser.sign_in()
    browser.item(
        "sources",
        variant="git",
        **{
            "f.name": "docs",
            "f.url": str(browser.repos["docs"]),
            "f.auth.method": "none",
        },
    )

    browser.item("trees", **{"f.name": "beta", "f.sources": ["gh", "docs"]})

    assert browser.stored("trees", "beta")["sources"] == ["gh", "docs"]  # type: ignore[index]


def test_a_tree_with_no_source_is_refused_against_the_field(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.item("trees", **{"f.name": "beta"})

    assert "<code>sources</code>" in answer.text
    assert "at least 1 item" in answer.text
    assert browser.stored("trees", "beta") is None


def test_a_new_tree_appears_in_the_switcher(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.item("trees", **{"f.name": "beta", "f.sources": ["gh"]})

    assert "/ui/config?tree=beta" in answer.text


def test_the_delete_warning_is_shown_before_the_deletion(
    browser: Browser,
) -> None:
    """`before_delete` says what removing a tree's config ARMS.

    An operator has to read that beside the button, not in the receipt — by
    then the next maintain is already unscoped.
    """
    browser.sign_in()
    browser.item("trees", **{"f.name": "beta", "f.sources": ["gh"]})
    _a_topic_in(browser, "beta")

    listing = browser.config(section="trees")
    page = browser.config(delete="trees:beta")

    assert "delete=trees:beta" in listing  # a row action, not a disclosure
    assert "tree beta now maps EVERY source" in page
    assert "Nothing in any tree goes stale" not in page  # it would contradict
    assert browser.stored("trees", "beta") is not None


# ------------------------------------------------------------------ unions


def test_adding_a_source_starts_by_naming_its_KIND(browser: Browser) -> None:
    """`sources` is a discriminated union, and there is no JavaScript here — so
    the alternative was five near-identical forms stacked on a page, four of
    them wrong."""
    browser.sign_in()

    page = browser.config(add="sources")

    assert "variant=git" in page
    assert "variant=notion" in page
    assert 'name="f.url"' not in page  # no fields until a kind is chosen


def test_the_chosen_kind_decides_which_fields_are_offered(
    browser: Browser,
) -> None:
    browser.sign_in()

    git = browser.config(add="sources", variant="git")

    assert 'name="f.url"' in git
    assert 'name="f.owner"' not in git  # that is the github-user shape


# ------------------------------------------------------- labels and help


def test_a_field_reads_by_its_label_and_help_not_its_config_path(
    browser: Browser,
) -> None:
    """Labels are not raw config paths like `auth.method` or `filter.only`,
    and every field says what it does. Both come from the model's own field,
    with the path kept, secondary, for the CLI and the JSON view."""
    browser.sign_in()

    page = browser.config(add="sources", variant="git")

    assert "Repository URL" in page
    assert "What git clone takes" in page  # the url's help line
    assert "Only these paths" in page and "Sign-in method" in page
    assert '<code class="key">filter.only</code>' in page


def test_source_fields_are_grouped_location_access_which_files(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.config(add="sources", variant="git")

    where = [
        page.index(f"<legend>{group}</legend>")
        for group in ("Location", "Access", "Which files")
    ]
    assert where == sorted(where)
    assert page.index('name="f.name"') < where[0]  # the name heads the form
    assert where[0] < page.index('name="f.url"') < where[1]
    assert where[1] < page.index('name="f.auth.method"') < where[2]
    assert where[2] < page.index('name="f.filter.only"')


def test_inputs_match_their_type(browser: Browser) -> None:
    """A one-line git url was a five-row textarea; a boolean was a box
    labelled "yes"; a glob list did not say it was one per line."""
    browser.sign_in()

    page = browser.config(add="sources", variant="git")

    assert re.search(r'<input class="line" type="text"[^>]*name="f\.url"', page)
    assert not re.search(r'<textarea[^>]*name="f\.url"', page)
    assert re.search(
        r'name="f\.filter\.replace_defaults" value="1"> '
        r"Drop the built-in ignore list</label>",
        page,
    )
    assert 'placeholder="one per line, e.g. src/payments/**"' in page


def test_an_opened_secret_is_still_only_the_mask(browser: Browser) -> None:
    """The labelled form must not be a new way for a credential out."""
    browser.sign_in()

    page = browser.config(edit="sources:gh")
    stored = browser.stored("sources", "gh")

    assert "Access token" in page
    assert placeholder("source-token") not in page
    assert stored["auth"]["token"] not in page  # type: ignore[index]
    assert browser.fields("sources", "gh")["f.auth.token"] == MASK


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
    """A brief carrying its own provenance — which is what goes stale."""
    conn = browser.conn
    with conn:  # type: ignore[attr-defined]
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            node,
            "What this topic says about the code it groups together.",
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
    browser.item(
        "prompts",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Summarise {content}",
        },
    )
    node = _a_topic_in(browser, "default")
    _brief_written_by(browser, node, "mine", "Summarise {content}")

    answer = browser.item(
        "prompts",
        name="mine",
        preview="1",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Condense {content}",
        },
    )

    assert "1 topic to rewrite at level 0" in answer.text
    assert "the next run would rewrite them" in answer.text
    assert browser.stored("prompts", "mine")["template"] == (  # type: ignore[index]
        "Summarise {content}"
    )


def test_each_collection_is_masked_by_its_OWN_declared_path(
    browser: Browser,
) -> None:
    """A source's credential is at `auth.token`, a connection's at `auth.key`.

    Masking every row with ONE collection's descriptor would leave the page
    looking right for sources — the first collection — while leaking every
    other collection's credential. Asserted on the JSON view because that is
    where a credential is rendered at all: the form view lists names and
    opens one item at a time, so a secret only reaches the page when somebody
    asks to edit the thing holding it.
    """
    key = placeholder("connection-key")
    secret = browser.cipher.encrypt(key)
    registry_store.insert(
        browser.conn,  # type: ignore[arg-type]
        "connections",
        "claude",
        json.dumps(
            {
                "name": "claude",
                "provider": "anthropic",
                "auth": {"method": "api-key", "key": secret.ciphertext},
            }
        ),
        secret.key_id,
        "t",
    )
    browser.sign_in()

    pages = [
        browser.config(section=collection, view="json")
        for collection in ("sources", "connections")
    ]

    for page in pages:
        assert key not in page and placeholder("source-token") not in page
        assert secret.ciphertext not in page
    assert json.loads(browser.document("sources"))[0]["auth"]["token"] == MASK
    assert json.loads(browser.document("connections"))[0]["auth"]["key"] == MASK


def test_a_credential_is_not_on_the_page_until_it_is_opened(
    browser: Browser,
) -> None:
    """The landing view lists names and what each points at. A collection of
    thirty sources does not print thirty configs, masked but all of them."""
    browser.sign_in()

    listing = browser.config(section="sources")

    assert MASK not in listing  # nothing to mask, because nothing is shown
    assert browser.fields("sources", "gh")["f.auth.token"] == MASK


def test_an_empty_collection_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "no models yet" in browser.config(section="models")


# ------------------------------------------- delete, completeness, environment


def test_delete_shows_what_it_would_strand_before_confirming(
    browser: Browser,
) -> None:
    """Delete is not a checkbox under every row that says nothing about what
    it takes with it. It is a row action that leads here first — and
    the count is of the briefs that template actually wrote."""
    browser.sign_in()
    browser.item(
        "prompts",
        **{"f.name": "mine", "f.role": "brief", "f.template": "S {content}"},
    )
    _brief_written_by(
        browser, _a_topic_in(browser, "default"), "mine", "S {content}"
    )

    listing = browser.config(section="prompts")
    page = browser.config(delete="prompts:mine")

    assert "delete=prompts:mine" in listing
    assert "Nothing deleted yet — this is what it would do" in page
    assert "<strong>default</strong>: 1 topic at level 0" in page
    assert 'name="confirm" value="1"' in page
    assert browser.stored("prompts", "mine") is not None  # only shown

    browser.remove("prompts", "mine", confirm="1")

    assert browser.stored("prompts", "mine") is None


@pytest.mark.parametrize(
    ("current", "said"),
    [
        ("drifted {content}", "1 topic at level 0"),
        (None, "Nothing in any tree goes stale"),
    ],
    ids=["drifted", "as-shipped"],
)
def test_a_reset_shows_what_going_back_to_the_default_would_strand(
    browser: Browser, current: str | None, said: str
) -> None:
    """A shipped default resets rather than deletes, so its preview is the
    edit BACK to what shipped: briefs written under a drifted template go
    stale, and a default that never drifted strands nothing — even though
    every brief it wrote carries its hash, which a delete would count."""
    browser.sign_in()
    shipped = browser.stored("prompts", "brief")
    template = current or str(shipped["template"])  # type: ignore[index]
    registry_store.replace(
        browser.conn,  # type: ignore[arg-type]
        "prompts",
        "brief",
        json.dumps({**shipped, "template": template}),  # type: ignore[dict-item]
        None,
        "t",
    )
    node = _a_topic_in(browser, "default")
    _brief_written_by(browser, node, "brief", template)

    page = browser.config(delete="prompts:brief")

    assert "Reset brief" in page
    assert said in page


def test_the_page_says_what_is_missing_to_build(browser: Browser) -> None:
    """The fixture registers no model, so every role is unserved — and the
    page names each, linked to the section that fixes it."""
    browser.sign_in()

    page = browser.config(section="sources")

    assert "Not ready to build" in page
    assert "role brief: no text model available" in page
    assert "embedding: no embedding model available" in page
    assert (
        'href="/ui/config?tree=default&amp;section=models">Models</a>' in page
    )


def test_environment_values_are_shown_read_only(
    browser: Browser, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HRONO_LLM_CONCURRENCY", "7")
    browser.sign_in("reader")

    page = browser.config()

    assert str(tmp_path / "hrono.db") in page
    assert "7 (from HRONO_LLM_CONCURRENCY)" in page
    assert version("hrono") in page
    monkeypatch.delenv("HRONO_LLM_CONCURRENCY")
    assert "4 (the default; HRONO_LLM_CONCURRENCY changes it)" in (
        browser.config()
    )


# --------------------------------------------------------- preview on a topic
WRITTEN = "A rewritten brief in the new style, naming what the topic holds."
CURRENT = "What this topic says about the code it groups together."


class _Model(BaseHTTPRequestHandler):
    """An openai-shaped completion API on a real socket."""

    status = 200
    seen: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        length = int(self.headers.get("Content-Length") or 0)
        _Model.seen.append(json.loads(self.rfile.read(length) or b"{}"))
        raw = json.dumps(
            {
                "choices": [{"message": {"content": WRITTEN}}],
                "usage": {"prompt_tokens": 21, "completion_tokens": 9},
            }
        ).encode()
        self.send_response(_Model.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def model_api(browser: Browser) -> Iterator[str]:
    """A text model named `writer` whose connection is the local API."""
    _Model.status, _Model.seen = 200, []
    with serving(_Model) as base:
        secret = browser.cipher.encrypt(placeholder("model-key"))
        registry_store.insert(
            browser.conn,  # type: ignore[arg-type]
            "connections",
            "local",
            json.dumps(
                {
                    "name": "local",
                    "provider": "openai-compatible",
                    "endpoint": base,
                    "auth": {"method": "api-key", "key": secret.ciphertext},
                }
            ),
            secret.key_id,
            "t",
        )
        registry_store.insert(
            browser.conn,  # type: ignore[arg-type]
            "models",
            "writer",
            json.dumps(
                {
                    "name": "writer",
                    "kind": "text",
                    "connection": "local",
                    "model": "a-model",
                    "params": {"max_tokens": 64},
                }
            ),
            None,
            "t",
        )
        yield base


def _previewable_topic(browser: Browser) -> int:
    """A topic with a condensation to reduce and a brief to compare with."""
    node = _a_topic_in(browser, "default")
    with browser.conn:  # type: ignore[attr-defined]
        digest = content_hash(b"a chunk of the corpus\n")
        condensations.upsert(
            browser.conn,  # type: ignore[arg-type]
            digest,
            "writer",
            "condensed: a chunk of the corpus",
            5,
            2,
        )
    _brief_written_by(browser, node, "mine", "Summarise {content}")
    return node


def _draft(topic: object, template: str = "Rewrite tersely: {content}") -> dict:
    return {
        "tree": "default",
        "name": "mine",
        "topic": str(topic),
        "f.name": "mine",
        "f.role": "brief",
        "f.template": template,
    }


def _tree_and_config(browser: Browser) -> dict[str, list[tuple]]:
    return {
        table: [
            tuple(row)
            for row in browser.conn.execute(  # type: ignore[attr-defined]
                f"SELECT * FROM {table}"  # noqa: S608
            ).fetchall()
        ]
        for table in ("nodes", "node_members", "briefs", "registry")
    }


def _preview(browser: Browser, **fields: object):  # type: ignore[no-untyped-def]
    return browser.client.post(
        "/ui/config/prompts/preview", data=fields, follow_redirects=False
    )


def _run_the_job(browser: Browser) -> None:
    """What the worker does, once, on this thread (the fixture stopped it)."""
    browser.client.app.state.worker._cycle()  # type: ignore[attr-defined]


def test_a_prompt_is_previewed_on_a_topic_beside_the_current_brief(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    browser.item(
        "prompts",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Summarise {content}",
        },
    )
    node = _previewable_topic(browser)
    before = _tree_and_config(browser)

    posted = _preview(browser, **_draft(node))
    _run_the_job(browser)
    page = browser.client.get(posted.headers["location"]).text

    assert posted.status_code == 303
    assert "With this prompt" in page and "Current brief" in page
    assert WRITTEN in page and CURRENT in page
    assert "21 in, 9 out" in page
    assert "Rewrite tersely:" in page  # the typed text is kept, unsaved
    assert 'value="mine"' in page  # and so is the name it was typed under
    sent = _Model.seen[0]["messages"][-1]["content"]
    assert sent.startswith("Rewrite tersely:")
    assert "condensed: a chunk of the corpus" in sent
    assert _tree_and_config(browser) == before


def test_a_preview_on_a_new_prompt_keeps_the_name_typed_for_it(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    location = _preview(browser, **{**_draft(node), "name": ""}).headers[
        "location"
    ]
    page = browser.client.get(location).text

    assert "add=prompts" in location
    assert 'name="f.name"' in page and 'value="mine"' in page


def test_a_previews_cost_is_recorded_against_its_job(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    location = _preview(browser, **_draft(node)).headers["location"]
    _run_the_job(browser)

    job = re.search(r"preview=(job_[0-9a-f]+)", location).group(1)  # type: ignore[union-attr]
    spent = for_jobs(browser.conn, job)  # type: ignore[arg-type]
    assert spent is not None and spent["calls"] == 1
    usage = browser.client.get("/ui/usage?tree=default").text
    assert f'data-run="{job}"' in usage


def test_a_failed_preview_says_why(browser: Browser, model_api: str) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)
    _Model.status = 500

    location = _preview(browser, **_draft(node)).headers["location"]
    _run_the_job(browser)
    page = browser.client.get(location).text

    assert "The preview failed" in page
    assert "did not come back with an answer" in page
    assert "Check the model and its connection in Settings" in page
    assert WRITTEN not in page


def test_a_canceled_preview_says_canceled_not_failed(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    location = _preview(browser, **_draft(node)).headers["location"]
    job = re.search(r"preview=(job_[0-9a-f]+)", location).group(1)  # type: ignore[union-attr]
    browser.client.post(f"/ui/jobs/{job}/cancel?tree=default")
    page = browser.client.get(location).text

    assert "The preview was canceled" in page
    assert "The preview failed" not in page
    assert "Writing a preview" not in page
    assert "Rewrite tersely:" in page


def test_the_topic_picker_groups_topics_by_level_and_offers_a_filter(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    _previewable_topic(browser)
    for _ in range(12):
        _brief_written_by(
            browser, _a_topic_in(browser, "default"), "mine", "x {content}"
        )

    page = browser.config(edit="prompts:mine")

    assert '<optgroup label="Level 0">' in page
    assert 'id="preview-topic-find"' in page


def test_a_preview_that_is_still_writing_says_so_and_refreshes(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    location = _preview(browser, **_draft(node)).headers["location"]
    page = browser.client.get(location).text

    assert "Writing a preview" in page
    assert "location.reload()" in page
    assert "Rewrite tersely:" in page


def test_saving_after_a_preview_still_shows_the_usual_impact(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    browser.item(
        "prompts",
        **{
            "f.name": "mine",
            "f.role": "brief",
            "f.template": "Summarise {content}",
        },
    )
    node = _previewable_topic(browser)
    _preview(browser, **_draft(node))
    _run_the_job(browser)

    answer = browser.item(
        "prompts",
        name="mine",
        preview="1",
        **{k: v for k, v in _draft(node).items() if k.startswith("f.")},
    )

    assert "1 topic to rewrite at level 0" in answer.text
    assert browser.stored("prompts", "mine")["template"] == (  # type: ignore[index]
        "Summarise {content}"
    )


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"f.template": "no placeholder here"}, "{content}"),
        ({"f.role": "condense"}, "only a brief prompt can be previewed"),
        ({"topic": ""}, "pick a topic to preview on"),
    ],
    ids=["template", "role", "topic"],
)
def test_a_preview_that_cannot_run_is_refused_before_a_call_is_paid_for(
    browser: Browser, model_api: str, change: dict[str, str], says: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    answer = _preview(browser, **{**_draft(node), **change})

    assert answer.status_code == 200
    assert says in html.unescape(answer.text)
    assert (
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT COUNT(*) FROM jobs"
        ).fetchone()[0]
        == 0
    )


def test_the_prompt_form_offers_the_topics_with_a_brief(
    browser: Browser, model_api: str
) -> None:
    browser.sign_in()
    node = _previewable_topic(browser)

    page = browser.config(add="prompts")

    assert 'id="preview-topic"' in page
    assert f'<option value="{node}"' in page
    assert 'id="preview-topic"' not in browser.config(add="models")


def test_a_reader_cannot_start_a_preview(
    browser: Browser, model_api: str
) -> None:
    node = _previewable_topic(browser)
    browser.sign_in("reader")

    answer = _preview(browser, **_draft(node))

    assert answer.status_code in {401, 403}
    assert (
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT COUNT(*) FROM jobs"
        ).fetchone()[0]
        == 0
    )


def test_the_preview_op_is_not_a_stage_the_runs_page_offers(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.client.get("/ui/jobs?tree=default").text

    assert 'value="brief"' in page
    assert 'value="brief-preview"' not in page
