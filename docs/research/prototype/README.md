# Prototype notebooks

The research notebooks and scripts hrono's recipes came from, kept for
reference. They are not runnable as-is: they read a local `.hrono/` research
database and clone cache that are not in the repository, and their outputs are
stripped. The settled results live in [`../../architecture.md`](../../architecture.md),
[`../../clustering.md`](../../clustering.md) and
[`../../summarization.md`](../../summarization.md).

| File | What it settled |
|---|---|
| `repo-analysis.ipynb` | Per-category section budgets, from file-size distributions of large repos |
| `paragraph-split.ipynb`, `structure-split.ipynb`, `structuring.py` | Structure-aware splitting (tree-sitter tree, delimiter cascade, greedy packer) |
| `model-comparison.ipynb`, `benchmark_embedding_models.py`, `test_embedding_models.py` | The embedding model choice |
| `research.ipynb`, `build_clusters.py` | The clustering recipe (content+path blend, UMAP, HDBSCAN leaf, noise attach) |
| `edit-stability.ipynb` | Whether in-place edits keep sections in their topics |
| `storage-v2.ipynb` | Passages as the stored ground truth |
| `rag-retrieval.ipynb`, `rag-summaries.ipynb` | Recall over passages and over briefs |
| `tree-level1.ipynb`, `tree-build.ipynb`, `summarize-level2-experiments.ipynb` | Building the tree and the upper-level brief prompt |
| `summarize_experiments.py`, `build_report.py`, `check_faithfulness.py` | The summarization experiments and the mechanical faithfulness check |
| `update-threshold.ipynb` | How far a change climbs the tree |
| `*.toml` | The prototype's configuration |
