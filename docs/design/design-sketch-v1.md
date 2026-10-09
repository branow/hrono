# hrono — draft

Sources: git repos (hundreds), Contentful (spaces/models/entries), Confluence (unstructured docs)

Pipeline:
1. split into chunks
2. cluster chunks -> communities (layer 1)
3. summarize each community
4. cluster communities -> higher communities, summarize, repeat to root

Update:
- each chunk stores pointer to source version (git: file+hash; Contentful: entry+version; Confluence: page+version)
- each summary stores pointers to its child chunks/nodes
- change -> rebuild chunk -> walk stored parent pointers up -> rebuild only that path -> stop
- tree with stored parent/child pointers, not graph + emergent clustering (avoids GraphRAG blast radius problem)

Chunk path/URI: <source-type>://<instance>/<path-segments...>[#sub-part][@version]
- git://github.com/acme-corp/payments-service/src/api/handlers/checkout.py#calculateTax@a1b2c3d
- contentful://space-abc123/environment-master/blogPost/entry-xyz789#field-body@v12
- confluence://mycompany.atlassian.net/space-ENG/page-123456#Deployment-Steps@v7

`<source-type>` is the resource's content model (a commit-addressable git file
tree / a CMS entry+field / a wiki page) — never the access or auth mechanism
used to fetch it. Two `hrono.toml` sources for the same repo via SSH vs HTTPS
(or, later, a non-clone fetch of the same repo) must resolve to the identical
`git://host/org/repo` URI, since the resource being referenced hasn't changed.
Access method is config (`hrono.toml`'s per-source `auth` field), never part
of the URI — if it leaked into the scheme, the same chunk could get two
different identities depending on how it happened to be fetched, breaking
dedup and the parent-pointer update mechanism above.

Chunking: recursive/hierarchical delimiter splitting (LangChain RecursiveCharacterTextSplitter style), target size per source-type (code ~1-2k chars, docs/CMS ~3-6k chars), tune empirically. Each chunk stores content hash (SHA-256) for change detection.

Clustering: HDBSCAN (absolute threshold, not fixed-k), custom similarity = α·path_similarity + (1-α)·semantic_similarity (path_similarity = shared prefix ratio, semantic = cosine of embeddings), α tuned via eval set. Node can have multiple parents (DAG), duplication intended. Embeddings persisted, reused, only changed chunks re-embedded. Scale: ANN index (FAISS/HNSW) not full O(n^2).

Branching factor: cost(b) = log_b(N) * (F + b*s), F = fixed hop cost, s = cost per extra sibling. No universal b — measure real F/s, pick b empirically.

Target scale/shape: ~1,000,000 chunks. Non-uniform branching per level, narrow at root / wide at leaves (wrong turn at root wastes whole traversal; wrong pick among leaves costs ~nothing). Locked ratio: 20/100/500 (3 levels). Alt: 10/20/50/100 (4 levels).

Clustering needs both a max cap AND a min floor per level (not just max) — else HDBSCAN's organic hierarchy drifts away from the target ratio/depth.

Incremental re-clustering: use Incremental DBSCAN (Ester et al. 1998, see `incdbscan` package), not full HDBSCAN, run independently per fixed level. Plain DBSCAN's incremental update is real/proven (insert/delete a point, only local neighborhood recomputed); full HDBSCAN's incremental story is weak (built-in predict only assigns into existing clusters, can't form new ones). Since we already lock a target branching factor per level anyway, per-level incremental DBSCAN fits better than relying on HDBSCAN's automatic hierarchy discovery.

Open:
- chunk boundary definition per source type
- new chunk -> which community, re-cluster siblings?
- change breaks community membership -> what happens
- raw-chunk fallback for detail queries
- clustering evaluation: eval set (queries + expected nodes) for task-based scoring; silhouette/DBCV for quick screening
