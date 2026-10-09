# index integrity

- distinct content hashes: 1638
- embeddings rows: 1638
- embed-once per (hash, model) holds: True
- every content embedded exactly once: True
- orphan contents (referenced by nothing): 76

- passages: 1514
- passages_fts rows: 1514
- fts in sync: True

## fts probe: MATCH 'unsign'
  - passage_id=837 '\nVersion 2.1.2\n-------------\n\nReleased 2022-03-24\n\n-   Handle date ove'
  - passage_id=838 '\nVersion 2.1.1\n-------------\n\nReleased 2022-03-09\n\n-   Handle date ove'
  - passage_id=846 '    using ``TimestampSigner.unsign(return_timestamp=True)`` or\n    ``B'
  - passage_id=1070 'For example, this is a serializer that signs using SHA-512, but will\nu'
  - passage_id=1074 'The signature is appended to the string, separated by a dot. To valida'

## embedding blobs
  - minilm dims=384: n=1638 blob bytes min=1536 max=1536 (expect 1536)

## orphan contents (referenced by no section and no passage)
count=76 total bytes=1327
  - 1db80d83738b 41B b'source/vendor/supports-color/browser.d.ts'
  - d8932363f624 39B b'source/vendor/supports-color/index.d.ts'
  - 54fc6024adde 39B b'source/vendor/supports-color/browser.js'
  - 78f27b13b17a 37B b'source/vendor/supports-color/index.js'
  - cde5b6844802 36B b'source/vendor/ansi-styles/index.d.ts'
  - ba029b4ec923 34B b'source/vendor/ansi-styles/index.js'
  - be8f4b093e4a 34B b'.devcontainer/on-create-command.sh'
  - f6384f9d8824 34B b'docs/_static/itsdangerous-icon.svg'
  - 3ece0a3951db 34B b'docs/_static/itsdangerous-logo.svg'
  - 1c45f085fff5 34B b'docs/_static/itsdangerous-name.svg'
  - 24ad71c8613d 31B b'.devcontainer/devcontainer.json'
  - b91b387e77f0 30B b'src/itsdangerous/serializer.py'

## are orphan bodies whole files? (match a cache file byte length)
orphans whose byte_len equals some cache file size: 6/76
orphans that are exactly a whole source file: 0

## resolution: the 76 "orphans" are path embeddings, by design

`src/hrono/cluster/blend.py:register_path_bodies` stores each distinct
repo-relative path string as a `contents` body so the path component of the
path-blended clustering vector (T17, alpha 0.5) embeds once per model, keyed by
the same content hash. 78 ingested files -> 76 distinct path strings (two paths
repeat across repos). Not a defect; noted so that any future "orphan content"
cleanup does not delete them.

- real content rows: 1638 - 76 = 1562 (92 section bodies + 1514 passage bodies,
  with 44 collapsed by cross-repo/identical-body dedup)
