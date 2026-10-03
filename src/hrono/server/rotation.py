"""Rotating the master key of a RUNNING server (#177).

``crypto.rotate`` re-encrypts the rows; this also moves the process onto the
new key, under the same write lock. Writers seal their secrets under that lock
too, so none can land between the two. Left on the old key, a secret saved
before the restart would be tagged with a key_id the next start refuses: a
half-rotated database.
"""

from __future__ import annotations

from fastapi import FastAPI

from hrono.crypto.rotate import Rotation, rotate


def rotate_running(app: FastAPI, old_key: bytes, new_key: bytes) -> Rotation:
    """Rotate the database and switch this server to ``new_key``.

    A refused rotation raises before anything is swapped, so the running key is
    unchanged.
    """
    with app.state.db.write() as conn:
        result = rotate(conn, old_key, new_key)
        app.state.cipher.rekey(new_key, result.key_id)
        app.state.key_id = result.key_id
    return result
