"""Answer one question against one tree, with someone waiting.

The API's recall route and the panel's Ask page are the same request: resolve
the embedding model, take the query encoder only if it is already in memory,
and run the frozen recipe. One function, so the page cannot show something an
agent would not receive.
"""

from __future__ import annotations

from hrono.db.database import Database
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import Encoder, ready_encoder_for
from hrono.errors import Unavailable
from hrono.recall import engine


def ask(
    database: Database,
    tree: str,
    question: str,
    limit: int,
    *,
    pages: bool = False,
) -> engine.Recall:
    """Recall for ``question`` in ``tree``; Unavailable while the model loads.

    A missing or broken embedding backend raises ``EmbedError`` with what is
    wrong, so the caller can say what to do rather than wait.
    """
    with database.connect() as conn:
        model = resolve_embedding_model(conn, {})
    encode = _query_encode(str(model["model"]))
    with database.connect() as conn:
        return engine.recall(
            conn,
            question,
            str(model["name"]),
            encode,
            limit=limit,
            tree=tree,
            pages=pages,
        )


def _query_encode(model_id: str) -> Encoder:
    """The query encoder, if it is ready; otherwise say so and do not wait.

    A question has someone waiting on it, so it does not queue behind a load it
    cannot see — it reports that the model is still arriving and asks them back.
    The miss starts the load, so "shortly" is true rather than
    hopeful.
    """
    encoder = ready_encoder_for(model_id)
    if encoder is None:
        raise Unavailable(
            f"the embedding model is still loading ({model_id}); "
            f"recall will answer once it is in memory"
        )
    return encoder
