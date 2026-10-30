---
id: E052
title: upper briefs state the conventions their children share, and where siblings differ
priority: medium
depends_on: []
requirements: []
---

## Goal
An agent reads the map top down and stops after the area brief and one or two
leaves. A rule that only some leaves carry never reaches it. Found on a
private-corpus implementation eval (2026-10-30, kept outside the repository):
older members of a family of procedures net refunds through a return-order
key, newer ones only exclude return orders. One leaf brief stated the older
rule eight times, the area brief above it never did, and no agent run opened
that leaf, so every run copied the newer pattern and missed refunds.

This is a prompt change. It is held until enough prompt changes collect to
justify one rebuild of a tree; do not ship it alone.

## Tickets

### 521 the brief-upper prompt asks for shared conventions and sibling differences
Problem: an upper brief summarises flows and parts, but not the rules its
children apply in common (time handling, status and order-type filters, how
history is read) or where siblings that do the same job disagree.
Done when: the `brief-upper` prompt asks for a short "Conventions" part: each
rule most children follow, with the condition, and each sibling that does the
same job differently, named, with how it differs. Measured on a tree whose
leaves disagree on such a rule: the area brief names both variants and the
leaves that carry each.

## Log
- 2026-10-30: proposed from the eval; parked until the next prompt batch.
