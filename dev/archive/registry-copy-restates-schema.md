# the delete preview's registry copy restates the schema by hand

From qa, E006 round 3 (non-blocking): `completeness._registry_without`
(src/hrono/registry/completeness.py) builds its in-memory copy with
hand-written CREATE TABLEs and never closes the connection. A registry
migration will silently drift from it. Build the copy from the real schema
(e.g. `sqlite3` backup of the registry tables, or the migration DDL) and close it.
