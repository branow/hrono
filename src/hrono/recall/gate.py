"""Recall's gate: answer only a question the tree has the words for.

Similarity alone cannot say "this corpus does not cover that": every question
has a nearest passage, and on bcreg "How do I knit a cable stitch?" scored a
higher vector z than half the real architecture questions. What does tell
them apart is vocabulary. A question about the corpus is made of the
corpus's words; an off-topic one is not ("sourdough", "Hawking", "knit" occur
nowhere in BC Registries). Measured on bcreg
(docs/evaluations/2026-10-recall-queries/): 0.90 to 1.00 of a real
question's content words occur in the tree, 0.00 to 0.60 of an off-topic
one's. ``COVERAGE`` sits between them.

A content word is a token of three letters or more that is not a function
word. It occurs when one passage of the tree's FTS index has a word starting
with its stem: the word less a plural or tense ending, cut to ``STEM``
letters. The index does not stem, and "issued" must find "issues", "rules"
find "rule". On bcreg every one of the 36 architecture questions has 0.95 or
more of its words in the tree, and 9 of 10 off-topic questions 0.80 or less
(the tenth, a marathon training plan, is made of words the code uses).
"""

from __future__ import annotations

import re
import sqlite3

COVERAGE = 0.9
STEM = 5
_ENDINGS = ("ing", "ed", "s")

_TERM = re.compile(r"[A-Za-z0-9]+")

# Function words only: nothing domain-specific, so the list needs no
# re-derivation for a different corpus.
_STOPWORDS = frozenset(
    (
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "should",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    )
)


def words(question: str) -> tuple[str, ...]:
    """The question's content words, lowercased, once each."""
    return tuple(
        sorted(
            {
                term.lower()
                for term in _TERM.findall(question)
                if len(term) > 2 and term.lower() not in _STOPWORDS
            }
        )
    )


def coverage(
    conn: sqlite3.Connection,
    question: str,
    scope: frozenset[int] | None = None,
) -> float:
    """The share of the question's content words that occur in ``scope``."""
    found = words(question)
    if not found:
        return 0.0
    return sum(_occurs(conn, word, scope) for word in found) / len(found)


def answers(
    conn: sqlite3.Connection,
    question: str,
    scope: frozenset[int] | None = None,
) -> bool:
    """Whether the tree has the words for ``question``."""
    return coverage(conn, question, scope) >= COVERAGE


def stem(word: str) -> str:
    """The word less one plural or tense ending, at most ``STEM`` letters."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            word = word[: -len(ending)]
            break
    return word[:STEM]


def _occurs(
    conn: sqlite3.Connection, word: str, scope: frozenset[int] | None
) -> bool:
    rows = conn.execute(
        "SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ?",
        (f'"{stem(word)}"*',),
    )
    if scope is None:
        return rows.fetchone() is not None
    return any(int(row[0]) in scope for row in rows)
