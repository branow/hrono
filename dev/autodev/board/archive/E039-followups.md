# E039 followups (qa round 1, head 31b5f83)

- blob_link: the `host != "gitlab.com"` exception for a one-segment instance is untested (mutating it to `if "/" not in rest:` survives tests/ingest/test_blob_link.py), and a `gitlab.com/<owner>` instance gives a link with no repo; src/hrono/ingest/blob_link.py:33. Fix: drop the exception (no gitlab discovery exists) or return None for it, and pin it with a test.
- commit 31b5f83 has a body with a Co-Authored-By line; CONTRIBUTING wants one sentence, no body, no attribution. Fix: reword when the branch is next rewritten or squashed.
- tests import the private `_when` from hrono.server.ui.nodes to build expected stamps; tests/server/test_ui_node_edits.py:27. Fix: assert on the stored made_at formatted the way the page shows it, or move `_when` to a public helper.
- Commit c3e16fe also has a Co-Authored-By body; the rule is one sentence, no body, no attribution. Strip it when the branch is squashed or reworded.
- (po review) README says a section "from a GitHub, GitLab or Bitbucket repo" links to its file, but only github.com, gitlab.com and bitbucket.org hosts link; a self-hosted GitLab/Bitbucket shows the path alone. Fix: say "on github.com, gitlab.com or bitbucket.org" in README.md:112.
