# a brief's cost cannot be priced

From E010 qa finding 3. The topic page shows a brief's tokens, not its price:
a brief stores no job id and `llm_calls` has no node link, so nothing joins a
brief to the priced ledger row. Pricing it needs a migration (job id on the
brief, or a node link on llm_calls). Fold into T58 (#178, per-job cost/impact)
if that lands first.
