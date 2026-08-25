"""Recall (M5): rank stored passages for a query across two legs and fuse them.

The keyword leg (this package's ``fts``) ranks passages by BM25 over an FTS5
index of passage path + body; the vector leg ranks by the path-blended
similarity passages are already embedded for (#069). Later tickets add the leg
queries, RRF fusion, and the recall endpoint.
"""
