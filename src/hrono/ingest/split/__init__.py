"""Structure-aware splitting: raw file bytes to a byte-span structure tree.

``structure`` parses a file into a tree of byte spans (grammar nodes plus
synthetic delimiter nodes), the input the packer turns into sections and
passages. The tree tiles the file exactly, so reassembly is byte-identical.
"""

from hrono.ingest.split.node import Node
from hrono.ingest.split.tree import structure

__all__ = ["Node", "structure"]
