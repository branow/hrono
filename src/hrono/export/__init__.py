"""Export: render the stored tree into a flatter agent-facing tree.

The stored tree keeps whatever depth the data produced (many levels of small
topics); the exported tree is deliberately flatter — wide-and-shallow beats
narrow-and-deep because a traversal hop costs more than showing more siblings.
``collapse`` is the pure algorithm mapping the deep stored tree to <= N
agent-facing levels; ``render`` turns it into markdown and ``produce`` serves
it.
"""
