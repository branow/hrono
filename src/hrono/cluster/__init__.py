"""Clustering: build the path-blended vectors topics are grouped from.

A section's clustering vector blends what it says (content) with where it lives
(file path). ``blend`` produces that combined vector from the two component
vectors; the cluster build (later) reduces and groups them.
"""
