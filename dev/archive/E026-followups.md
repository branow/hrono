# E026 followups (qa round 1, minor)

- The setup hint says `pip install "hrono[embed]"`, but the README says `uv pip install "hrono[embed]"`. `src/hrono/embed/runner.py:33`: make `INSTALL` use the README's line, or change the README to match.
- In the models-step callout, the code span `uv sync --extra embed` breaks across two lines at 1100px. `src/hrono/server/templates/setup.html:81`: add `white-space: nowrap` to code spans inside the callout.
- `DEFAULT_TREE` in `src/hrono/registry/collections/trees.py:32` is one more copy of the "default" literal. Others are at `tree/update.py:101`, `tree/maintain.py:44`, `tree/settle.py:54`, `tree/sync_chain.py:54`, `summarize/brief_upper.py:46` and `cluster/*.py`. Import the one constant everywhere.
- When `/ui/setup/build` refuses a tree, it sends a browser form post a raw JSON 404 page (`src/hrono/server/ui/setup.py:238`). Only a hand-edited form can reach this, because the form posts a tree from `_trees`. Re-render the setup page with the message.
- `tests/server/test_trees.py:92` (`test_maintain_for_a_registered_tree_queues_a_job`) asserts only the 200. Also assert that a `jobs` row exists with `tree='alpha'`.
- (po) The models-step callout for a missing embed backend names only the install; an install that has an embedding connection could instead register a remote embedding model in Settings. `src/hrono/server/templates/setup.html:78`: add one line pointing to Settings > models for a remote embedder.
