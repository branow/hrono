# hrono docs

Read in this order:

1. [architecture.md](architecture.md): the system end to end, with the code
   that implements each part.
2. [api.md](api.md): the REST API and the CLI.
3. [clustering.md](clustering.md): how topics are built, updated, repaired
   and settled, with the constants and why.
4. [summarization.md](summarization.md): how briefs are written and when a
   change climbs the tree.
5. [dashboard.md](dashboard.md): the dashboard, page by page.

Background:

- [research/prior-art.md](research/prior-art.md): RAPTOR, GraphRAG,
  incremental indexing and agent memory systems, and where hrono differs.
- [research/summarization-prompts.md](research/summarization-prompts.md): the
  summarization prompts of existing hierarchical retrieval systems.
- [research/hop-cost.md](research/hop-cost.md): the measured cost of one
  traversal hop, behind the export's shape.
- [research/prototype/](research/prototype/): the notebooks the recipes came
  from.
- [evaluations/](evaluations/): real runs of hrono, each with its log, findings
  and metrics.
