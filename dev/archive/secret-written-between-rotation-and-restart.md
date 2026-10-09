# A secret written between a key rotation and the restart is on the old key

After `/admin/rotate-key` (or the Access page's rotate form) the running server
still holds the old cipher and key_id (`app.state.key_id`, `Cipher.from_key` in
`server/app.py`). A connection or source saved before the restart is encrypted
under the old key and tagged with the old key_id, so once the server restarts
on the new key that row raises `KeyMismatch`: the database is half-rotated, the
state `crypto/rotate.py` says is worse than unrotated. Either refuse secret
writes until restart, or swap the in-process cipher after a rotation.
Found gating E012; predates it (T59).
