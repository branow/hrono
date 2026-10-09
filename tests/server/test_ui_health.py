"""The Health page lists each problem and fixes it in place.

Every assertion about a fix reads the STORE after the click, never the page
that reports it. The placement test then runs the REAL `migrate` over the
topic it was placed in, because "survives a sync" is a claim about what the
pipeline does next, not about what the form posted.
"""

from __future__ import annotations

import json
import re

import pytest

from hrono import pins
from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.repair import migrate
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from tests.server.test_ui_surgery import (  # noqa: F401
    MODEL,
    TREE,
    Browser,
    _section,
)
from tests.server.test_ui_surgery import browser as _surgery_browser
from tests.summarize.test_shape import ECHOED, _default

browser = _surgery_browser


def _health(browser: Browser) -> str:
    return browser.client.get(f"/ui/trees/{TREE}/triage").text


def _park(browser: Browser, path: str, vector: list[float]) -> int:
    with browser.conn:  # type: ignore[union-attr]
        section = _section(browser.conn, path, vector)
        incubator.park(browser.conn, TREE, section, 1)  # type: ignore[arg-type]
    return section


def _held(browser: Browser, kind: str) -> frozenset[int]:
    return pins.pinned(browser.conn, kind)  # type: ignore[arg-type]


def test_a_waiting_section_shows_its_nearest_topic_and_score(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    _park(browser, "near-a.md", [0.95, 0.05])
    browser.sign_in()

    page = _health(browser)

    row = page.split("near-a.md", 1)[1].split("</tr>", 1)[0]
    nearest = row.split("</td>")[1]
    assert f"/nodes/{a}?" in nearest and f"/nodes/{b}?" not in nearest
    assert re.search(r'class="num">\d\.\d\d<', nearest)


def test_a_placement_made_from_the_list_survives_a_sync(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    # by proximity this section belongs with `a`; a person files it in `b`
    section = _park(browser, "near-a.md", [0.95, 0.05])
    browser.sign_in()

    answer = browser.post("triage/place", section=str(section), to_node=str(b))

    assert answer.status_code == 200 or answer.history  # followed redirect
    assert section in browser.members_of(b)
    assert incubator.count(browser.conn, TREE) == 0  # type: ignore[arg-type]
    assert section in _held(browser, pins.MEMBERSHIP)
    # the pipeline's own monitor, over the topic it was put in: the section
    # fits `a` better, so only the pin keeps it where the person put it
    with browser.conn:  # type: ignore[union-attr]
        moved = migrate(browser.conn, TREE, b, MODEL)  # type: ignore[arg-type]
    assert moved == 0
    assert section in browser.members_of(b)


def test_a_misfit_lists_where_it_sits_and_where_it_fits_and_moves(
    browser: Browser,
) -> None:
    a, _, c = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        stray = _section(browser.conn, "stray.md", [0.99, 0.0])
        cluster_store.add_member(
            browser.conn,  # type: ignore[arg-type]
            c,
            stray,
            forced=True,
            similarity=None,
        )
    browser.sign_in()

    row = _health(browser).split("stray.md", 1)[1].split("</tr>", 1)[0]
    browser.post("triage/place", section=str(stray), to_node=str(a))

    assert f"/nodes/{c}?" in row and f"/nodes/{a}?" in row
    assert stray in browser.members_of(a)
    assert stray not in browser.members_of(c)
    with browser.conn:  # type: ignore[union-attr]
        flagged = browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT forced FROM node_members WHERE section_id = ?", (stray,)
        ).fetchone()
    assert flagged["forced"] == 0


def test_a_stale_brief_says_why_and_regenerates_only_itself(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        briefs.upsert(
            browser.conn,  # type: ignore[arg-type]
            a,
            f"A summary of topic {a}, long enough to be a brief.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(
                browser.conn,  # type: ignore[arg-type]
                a,
            ),
            input_tokens=1,
            output_tokens=1,
        )
        briefs.mark_stale(browser.conn, a)  # type: ignore[arg-type]
    browser.sign_in()

    page = _health(browser)
    answer = browser.post("triage/regenerate", node=str(a))

    row = page.split(f"/nodes/{a}?", 1)[1].split("</tr>", 1)[0]
    assert "something beneath it changed" in row
    assert "it has no brief yet" in page.split(f"/nodes/{b}?", 1)[1]
    assert answer.url.path == "/ui/jobs"
    started = browser.conn.execute(  # type: ignore[attr-defined]
        "SELECT op, scope FROM jobs"
    ).fetchall()
    assert [(row["op"], row["scope"]) for row in started] == [
        ("brief", f'{{"node": {a}, "level": 0}}')
    ]


def test_a_settled_echo_says_a_person_must_write_it_and_offers_no_button(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    conn = browser.conn
    with conn:  # type: ignore[union-attr]
        registry_store.insert(
            conn,  # type: ignore[arg-type]
            "prompts",
            "brief",
            json.dumps({"name": "brief", "template": _default("brief")}),
            None,
            "t",
        )
        for node in (a, b):
            briefs.upsert(
                conn,  # type: ignore[arg-type]
                node,
                ECHOED["brief"],
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature=briefs.member_signature(conn, node),  # type: ignore[arg-type]
                input_tokens=1,
                output_tokens=1,
                flagged="echoes-the-prompt",
            )
        briefs.mark_stale(conn, b)  # type: ignore[arg-type]
    browser.sign_in()

    page = _health(browser)

    echo = page.split(f"/nodes/{a}?", 1)[1].split("</tr>", 1)[0]
    assert "a person must write this brief by hand" in echo
    assert "triage/regenerate" not in echo
    plain = page.split(f"/nodes/{b}?", 1)[1].split("</tr>", 1)[0]
    assert "triage/regenerate" in plain
    assert "must write" not in plain


@pytest.mark.parametrize(
    ("change", "said"),
    [
        ("stale", "something beneath it changed"),
        ("members", "its members changed"),
        ("prompt", "its prompt or model changed"),
        ("echo", "not a brief"),
    ],
)
def test_stale_why_names_the_cause(
    browser: Browser, change: str, said: str
) -> None:
    a, _, _ = browser.leaves
    conn = browser.conn
    with conn:  # type: ignore[union-attr]
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            a,
            f"A summary of topic {a}, long enough to be a brief.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, a),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
        )
        if change == "stale":
            briefs.mark_stale(conn, a)  # type: ignore[arg-type]
        if change == "members":
            conn.execute(  # type: ignore[attr-defined]
                "UPDATE briefs SET member_signature = 'old' WHERE node_id = ?",
                (a,),
            )
        if change == "echo":
            conn.execute(  # type: ignore[attr-defined]
                "UPDATE briefs SET text = ?, flagged = 'talks-back' "
                "WHERE node_id = ?",
                ("Could you tell me more?", a),
            )

    assert said in briefs.stale_why(conn, a)  # type: ignore[arg-type]


def test_a_fresh_or_held_brief_has_no_stale_reason(browser: Browser) -> None:
    a, b, _ = browser.leaves
    conn = browser.conn
    with conn:  # type: ignore[union-attr]
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            a,
            f"A summary of topic {a}, long enough to be a brief.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, a),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
        )
        briefs.mark_stale(conn, a)  # type: ignore[arg-type]
        pins.pin(conn, pins.BRIEF, a)  # type: ignore[arg-type]

    assert briefs.stale_why(conn, a) == ""  # type: ignore[arg-type]
    assert briefs.stale_why(conn, b) == "it has no brief yet"  # type: ignore[arg-type]


def test_an_upper_topic_regenerates_through_brief_upper(
    browser: Browser,
) -> None:
    left, _ = browser.uppers
    browser.sign_in()

    browser.post("triage/regenerate", node=str(left))

    started = browser.conn.execute(  # type: ignore[attr-defined]
        "SELECT op, scope FROM jobs"
    ).fetchall()
    assert [(row["op"], row["scope"]) for row in started] == [
        ("brief-upper", f'{{"node": {left}, "level": 1}}')
    ]


def test_every_hand_edit_is_listed_and_released_one_at_a_time(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    section = min(browser.members_of(a))
    with browser.conn:  # type: ignore[union-attr]
        pins.pin(browser.conn, pins.BRIEF, a, reason="named by hand")  # type: ignore[arg-type]
        pins.pin(browser.conn, pins.PARENTING, b, reason="moved by hand")  # type: ignore[arg-type]
        pins.pin(
            browser.conn,  # type: ignore[arg-type]
            pins.MEMBERSHIP,
            section,
            reason="filed by hand",
            anchor=a,
        )
    browser.sign_in()

    page = _health(browser)
    browser.post("triage/release", kind=pins.BRIEF, target=str(a))

    assert page.count("/triage/release") == 3
    for reason in ("named by hand", "moved by hand", "filed by hand"):
        assert reason in page
    assert _held(browser, pins.BRIEF) == frozenset()
    assert _held(browser, pins.PARENTING) == {b}
    assert _held(browser, pins.MEMBERSHIP) == {section}


def test_another_trees_edit_is_neither_listed_nor_released(
    browser: Browser,
) -> None:
    with browser.conn:  # type: ignore[union-attr]
        other = cluster_store.add_leaf_node(
            browser.conn,  # type: ignore[arg-type]
            "elsewhere",
            [(_section(browser.conn, "x.md", [1.0, 1.0]), False, None)],
        )
        pins.pin(browser.conn, pins.BRIEF, other, reason="not here")  # type: ignore[arg-type]
    browser.sign_in()

    page = _health(browser)
    answer = browser.post("triage/release", kind=pins.BRIEF, target=str(other))

    assert "not here" not in page
    assert "holds no brief edit" in answer.text
    assert _held(browser, pins.BRIEF) == {other}


def test_a_reader_sees_the_lists_and_no_controls(browser: Browser) -> None:
    a, _, _ = browser.leaves
    section = _park(browser, "near-a.md", [0.95, 0.05])
    with browser.conn:  # type: ignore[union-attr]
        pins.pin(browser.conn, pins.BRIEF, a, reason="named by hand")  # type: ignore[arg-type]
    browser.sign_in("reader")

    page = _health(browser)

    assert "near-a.md" in page and "named by hand" in page
    for action in ("/triage/place", "/triage/regenerate", "/triage/release"):
        assert action not in page
    assert section not in browser.members_of(a)


def test_every_health_write_refuses_a_reader_and_a_writer(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    section = _park(browser, "near-a.md", [0.95, 0.05])
    with browser.conn:  # type: ignore[union-attr]
        pins.pin(browser.conn, pins.BRIEF, a)  # type: ignore[arg-type]
    attempts = {
        "triage/place": {"section": str(section), "to_node": str(b)},
        "triage/regenerate": {"node": str(a)},
        "triage/release": {"kind": pins.BRIEF, "target": str(a)},
    }

    for role in ("reader", "writer"):
        browser.sign_in(role)
        refused = {
            path: browser.post(path, **fields).status_code
            for path, fields in attempts.items()
        }
        assert refused == dict.fromkeys(attempts, 403), role

    assert section not in browser.members_of(b)
    assert _held(browser, pins.BRIEF) == {a}
    assert browser.conn.execute("SELECT 1 FROM jobs").fetchone() is None  # type: ignore[attr-defined]


def test_a_misfits_nearer_topic_is_never_the_one_it_sits_in(
    browser: Browser,
) -> None:
    a, _, _ = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        snug = _section(browser.conn, "snug.md", [1.0, 0.01])
        cluster_store.add_member(
            browser.conn,  # type: ignore[arg-type]
            a,
            snug,
            forced=True,
            similarity=None,
        )
    browser.sign_in()

    row = _health(browser).split("snug.md", 1)[1].split("</tr>", 1)[0]

    assert f"/nodes/{a}?" in row.split("</td>")[1]
    assert f"/nodes/{a}?" not in row.split("</td>")[2]
