# hrono — implementation map (v0, no details)

One language: **Python** (chosen for integrations; revisit if another language catches up).
One protocol: **HTTP + JSON** between client and server.
Storage: **SQLite** on the server (fine at one writer / many readers; swappable later).

hrono is a platform: the knowledge tree is its first feature, not its definition.
Future features (e.g. indexes) plug into the same server, API, CLI, and admin panel.

## Server

The centralized part. Source of truth. Owns the database, all data, all compute,
all LLM calls. Multiple people connect to one server and reuse one knowledge base.

Layers, top to bottom:

- **Integrations** — everything external, behind ports defined by core:
  - *Sources*: git (v1); later Contentful, Notion, Confluence, …
  - *LLM providers*: Claude Agent SDK (v1); later raw Anthropic API, OpenAI, …
  - *Embedding*: local sentence-transformers (v1); later API providers.
- **Core** — feature-agnostic machinery: source sync, filtering,
  structure-aware splitting, identity (address / hash / structure path),
  storage, embedding management, configuration, and the **operations
  framework**: every pipeline stage is a named operation with a recorded run
  (inputs, config, status, cost) — idempotent, rerunnable, resumable.
- **Features** — each feature builds on core, supports multiple instances:
  - *Knowledge tree* (v1): clustering, briefing, update lifecycle, export rendering.
  - *Recall* (v1): retrieval index + the frozen recall recipe (query embedding included).
  - Future: indexes, ….
- **API** — the HTTP+JSON surface the client and admin panel talk to.
  Roles: reader / writer / admin (present from day one, enforcement minimal in v1).
- **Admin panel** — web UI (v1): inspect data and runs, rerun operations,
  browse trees and briefs, manage configuration.

## Client

A CLI tool installed locally. Thin: no models, no compute, no data of its own —
only a server connection and downloaded artifacts.

- **Setup**: connect to a server, authenticate, pick the working context
  (which knowledge tree / which feature) — `kubectl`-style.
- **Recall**: send a question, get passages with provenance (server does the work).
- **Export**: download a feature's artifact into the local file system —
  for the tree: plain files/folders an agent traverses locally. Server stays
  the source of truth; every user can hold a local copy.
- **Extensible**: each feature contributes its own subcommands.
- **Admin commands**: server management for admin-role users (panel's CLI twin).

## Explicitly deferred

- Real access control (beyond role stubs).
- Non-git sources, non-Anthropic LLM providers.
- Database swap (SQLite until it hurts).
- Build order — derived from this map once it's agreed.
