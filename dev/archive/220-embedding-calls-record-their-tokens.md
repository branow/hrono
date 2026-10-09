---
id: 220
title: remote embedding calls record the tokens the provider reports
priority: low
size: small
depends_on: [201, 202]
spec_refs: [#201, #202]
---

## Context
#201's `metered()` wraps every embedding encoder and records tokens as NULL, on the reasoning that "an embedding pass reports no tokens through this seam". That holds for the in-process model (`local`), but the openai-shaped `/v1/embeddings` response carries `usage.prompt_tokens`, and those calls are billed per token. With NULL tokens #202 can only report such a run's metered cost as unknown (after its kickback fix), never as a figure.

## Description
Have the openai embeddings path return its `usage.prompt_tokens` alongside the vectors and record them as `input_tokens` on the ledger row; add prices for the embedding models the table should know, or leave them to the per-model `price` override.

## Acceptance criteria
- [ ] a remote embedding batch writes its reported input tokens to its ledger row
- [ ] a local embedding batch still records NULL tokens
- [ ] `GET /usage` prices a remote embedding run when its model has a price

## Review log
- 2026-10-03 qa: filed while reviewing #202 (a remote embedding call showed METERED $0.0000).
- 2026-10-03 po: triaged — real and small, and without it a remote-embedding install shows cost as unknown forever. Promoted to todo.
