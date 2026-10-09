"""Tree-level operations: the whole-pipeline ``maintain`` easy-button.

``maintain`` runs the existing ops in dependency order over a tree — sync ->
split -> embed -> condense -> cluster -> brief -> recurse-to-root — so one
command (``POST /trees/<name>/maintain`` or ``hrono tree maintain <name>``)
builds the tree end to end. It orchestrates; it never reimplements an op.
"""
