"""Recall: the passages of a tree most like a question.

``gate`` refuses a question the tree has no words for, ``similarity`` ranks
source and brief passages by cosine, ``window`` keeps the best one per
document, and ``engine`` runs the recipe. ``fts`` is the keyword index the gate
reads.
"""
