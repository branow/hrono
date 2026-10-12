-- Clustering reads each section's source by its bytes and path (the folder
-- term of the clustering vector, src/hrono/cluster/blend.py); without an
-- index that is a scan of every section per section.

CREATE INDEX sections_content_hash ON sections (content_hash, path);
