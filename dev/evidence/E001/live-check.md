# E001 T2b: the condensation gate on a copy of ~/hrono-click (user)

Agents do not touch `~/hrono-click` or its key, so this check is yours to run.
It is the T2a e2e (`transcript.md`, `node-diff.json`) over your real corpus and
real provider. Run it against the merged head, on a COPY. Your live server on
:8900 keeps running and is never written to.

Cost: one condense call for each listed condensation, plus one brief call for
each topic above them and each of its ancestors. With the 4 known bad
condensations that is 4 condense calls and a handful of brief calls, through
whichever connection your `condense` and `brief` models use.

## 0. Set the variables

```sh
HRONO=/Users/orest/repos/hrono         # at the merged head: git -C $HRONO log -1
LIVE_DB=~/hrono-click/.hrono/hrono.db  # the db the :8900 server uses: its
                                       # --db, else <its cwd>/.hrono/hrono.db
COPY=~/hrono-click-e001                # a fresh directory; must not exist
TREE=default                           # the tree to check
PORT=8901
```

## 1. Copy the home without stopping the live server

`.backup` takes a consistent snapshot of a database that is open in WAL mode.
A `cp` of the file would not. The clone cache is copied so the sync does not
re-clone anything.

```sh
mkdir -p "$COPY/.hrono"
sqlite3 "$LIVE_DB" ".backup '$COPY/.hrono/hrono.db'"
cp -R "$(dirname "$LIVE_DB")/cache" "$COPY/.hrono/cache"
```

The master key is NOT copied. The copy's server reads it in place, read-only,
through `--key-file`.

## 2. Start a server on the copy

```sh
cd "$HRONO" && uv run hrono serve --port $PORT \
  --db "$COPY/.hrono/hrono.db" --key-file ~/hrono-click/master.key
```

Leave it running in its own terminal. The copy already has users, so it prints
no bootstrap token. Use the token you already use for :8900:

```sh
B=http://127.0.0.1:$PORT
H="Authorization: Bearer $(cat <your token file>)"   # or paste the token
```

## 3. List, snapshot, sync, snapshot, list

```sh
curl -s -H "$H" $B/trees/$TREE/unusable-condensations \
  | tee "$COPY/list-before.json" | jq '.count, [.condensations[].path]'

snap() {  # every condensation and every brief in the tree, by key
  sqlite3 -readonly -json "$COPY/.hrono/hrono.db" \
    "SELECT 'c:'||content_hash||':'||model_name AS k, text FROM condensations
     UNION ALL
     SELECT 'b:'||b.node_id, b.text FROM briefs b JOIN nodes n
       ON n.id = b.node_id WHERE n.tree = '$TREE' ORDER BY k" > "$1"
}
snap "$COPY/before.json"

JOB=$(curl -s -X POST -H "$H" $B/trees/$TREE/sync | jq -r .job_id)
until curl -s -H "$H" $B/jobs/$JOB | jq -e '.status != "pending"
  and .status != "running"' >/dev/null; do sleep 5; done
curl -s -H "$H" $B/jobs/$JOB | tee "$COPY/sync.json" | jq '.status,
  (.result.stages[] | select(.op=="update") | .result)'

snap "$COPY/after.json"
curl -s -H "$H" $B/trees/$TREE/unusable-condensations | jq .count
```

## 4. Read the diff

```sh
python3 - "$COPY" <<'EOF'
import json, sys
d = sys.argv[1]
b = {r["k"]: r["text"] for r in json.load(open(f"{d}/before.json"))}
a = {r["k"]: r["text"] for r in json.load(open(f"{d}/after.json"))}
listed = {c["content_hash"] for c in
          json.load(open(f"{d}/list-before.json"))["condensations"]}
changed = sorted(k for k in b.keys() & a.keys() if b[k] != a[k])
print("condensations changed:", [k for k in changed if k[0] == "c"])
print("  listed before:      ", sorted(listed))
print("briefs changed:", [k for k in changed if k[0] == "b"])
print("added:", sorted(a.keys() - b.keys()))
print("removed:", sorted(b.keys() - a.keys()))
print("identical:", sum(b[k] == a.get(k) for k in b))
EOF
```

## Pass when

- the first list has `count` 4 and names the 4 bad condensations;
- the job `succeeded`, and its `update` stage says `"changed": false`. If it
  says `true`, a source moved since the copy and the run also ingested that,
  so the brief diff is not only the gate's. Re-run on a fresh copy right
  after a sync of the live tree;
- `condensations changed` is exactly the 4 listed hashes, none of them talks
  back (the list after the sync is `count` 0), and nothing was added or
  removed;
- `briefs changed` is exactly the topics holding those sections plus their
  ancestors. Compute that set right after step 3's first list, BEFORE the
  sync:

```sh
python3 - "$COPY" <<'EOF'
import json, sqlite3, sys
d = sys.argv[1]
hashes = [c["content_hash"] for c in
          json.load(open(f"{d}/list-before.json"))["condensations"]]
conn = sqlite3.connect(f"file:{d}/.hrono/hrono.db?mode=ro", uri=True)
rows = conn.execute(
    "WITH RECURSIVE up(id) AS (SELECT m.node_id FROM node_members m "
    "JOIN sections s ON s.id = m.section_id WHERE s.content_hash IN "
    "(SELECT value FROM json_each(?)) UNION SELECT c.parent_id "
    "FROM node_children c JOIN up ON c.child_id = up.id) "
    "SELECT id FROM up ORDER BY id", (json.dumps(hashes),))
print("expected briefs:", ["b:%d" % r[0] for r in rows])
EOF
```

Then stop the copy's server and `rm -rf "$COPY"`.
