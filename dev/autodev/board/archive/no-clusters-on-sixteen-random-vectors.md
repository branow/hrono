# "clustering produced no clusters" reproduces on 16 sections of unstructured vectors

What: driving E002, a maintain over a 16-file repo with a stand-in embedding
endpoint (64-dim vectors from SHA-256 of the text, so no structure at all)
condensed all 16 sections and then failed at `cluster` with cluster-error
"clustering produced no clusters", every time.
Where: src/hrono/cluster/build.py (see E003 ticket 1).
Why it matters: may be a cheap reproducer for E003's ticket 1 — an all-noise
labelling on a small valid corpus. Input: 16 sections, 64 dims, uniform
pseudo-random in [-0.5, 0.5].
