# a sync right after server start can fail "the reduction failed"
`server/app.py` `_warm_query_encoder` imports torch on a thread at boot; a clustering job running meanwhile
makes scipy probe a half-imported torch and UMAP raises (seen in tests/server/test_manual_split.py as a 500).
Fix idea: import torch before starting the worker, or make the clustering wait for the load.

(po 2026-11-03: folded into E064 round 2.)
