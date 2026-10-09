# Changelog

All notable changes to hrono are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

The first release.

### Added

- Ingest from git repositories, GitHub users and organizations, Bitbucket
  workspaces, Confluence and Notion, split into sections and passages.
- In-process embedding and UMAP + HDBSCAN clustering into a tree of topics,
  each with an LLM-written brief, up to a single root.
- Incremental sync: a source change re-reads, re-places and re-summarizes only
  what it affects.
- Recall: the passages that answer a question, with provenance and a
  confidence floor.
- Export of a tree as a folder of Markdown an agent can walk, with a
  configurable hop limit.
- LLM providers: Claude Code, Anthropic, OpenAI and OpenAI-compatible servers.
- One `hrono` binary: an HTTP server that owns the SQLite database, and a CLI
  client for every operation.
- A web dashboard for browsing, asking, health review, manual edits with undo,
  guided setup, settings, access control and usage accounting.
- Role-based access (reader, writer, admin), secrets encrypted at rest, and
  master-key rotation.

[Unreleased]: https://github.com/branow/hrono/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/branow/hrono/releases/tag/v0.1.0
