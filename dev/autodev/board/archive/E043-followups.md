# E043 followups (qa round 1, head 32b0cd0)

- `panel()` returns `typed` as `object`, so `_render` needs a `# type: ignore[arg-type]` to rebuild the form - src/hrono/server/ui/settings.py:404 - have `preview.panel` return a typed shape (TypedDict or dataclass) so no ignore is needed.
- A canceled preview is shown as "The preview failed" with `failures.explain` over a job that has no error code - src/hrono/server/preview.py:50 - say it was canceled instead of running it through the failure explainer.
- The topic select lists every briefed topic in the tree, which is unwieldy on a large tree - src/hrono/server/preview.py:22 - group by level or offer a search, as the dev noted.
- The fix commit 45da64f carries a Co-Authored-By trailer, which goes against the no-attribution commit rule (qa.md section 8). Drop it if the merge rewrites the message. `git log -1 45da64f`
