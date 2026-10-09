> Run 1 of the same driver against efe8e40 (before the update.py fix), with the first 3-topic corpus. The list showed the 4 planted condensations and the sync re-condensed none of them: `update` skipped condense because no source changed.

# E001 T2a: the condensation gate over a real `hrono serve`

Scratch home `/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-1/home`, its own key from `hrono admin new-key`; provider: local openai-compatible stub on :54071.

## Setup and cold build

```
POST /connections
{
  "name": "stub",
  "provider": "openai-compatible",
  "endpoint": "http://127.0.0.1:54071/v1",
  "auth": {
    "method": "none"
  }
}
-> 201
{
  "name": "stub",
  "provider": "openai-compatible",
  "endpoint": "http://127.0.0.1:54071/v1",
  "auth": {
    "method": "none",
    "key": null
  }
}
```

```
POST /models
{
  "name": "stub-embed",
  "kind": "embedding",
  "connection": "stub",
  "model": "bow-64",
  "params": {
    "dims": 64
  }
}
-> 201
{
  "name": "stub-embed",
  "kind": "embedding",
  "connection": "stub",
  "model": "bow-64",
  "role": null,
  "params": {
    "dims": 64
  },
  "price": null
}
```

```
POST /models
{
  "name": "stub-text",
  "kind": "text",
  "connection": "stub",
  "model": "stub-1"
}
-> 201
{
  "name": "stub-text",
  "kind": "text",
  "connection": "stub",
  "model": "stub-1",
  "role": null,
  "params": {},
  "price": null
}
```

```
POST /sources
{
  "name": "corpus",
  "type": "git",
  "url": "/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-1/corpus",
  "auth": {
    "method": "none"
  }
}
-> 201
{
  "name": "corpus",
  "type": "git",
  "url": "/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-1/corpus",
  "auth": {
    "method": "none",
    "token": null,
    "key": null
  },
  "filter": null
}
```

```
POST /trees
{
  "name": "default",
  "sources": [
    "corpus"
  ]
}
-> 201
{
  "name": "default",
  "sources": [
    "corpus"
  ]
}
```

```
POST /trees/default/maintain
-> 200
{
  "job_id": "job_133cc7b3741d4852b61c305b59045264"
}
```

```
GET /jobs/job_133cc7b3741d4852b61c305b59045264
-> 200
{
  "id": "job_133cc7b3741d4852b61c305b59045264",
  "parent_id": null,
  "tree": "default",
  "op": "maintain",
  "scope": {},
  "status": "succeeded",
  "error": null,
  "result": {
    "tree": {
      "topics_added": 5,
      "topics_removed": 0,
      "sections_refiled": 0,
      "briefs_rewritten": 5
    },
    "stages": [
      {
        "op": "sync",
        "over": "corpus",
        "seconds": 0.06,
        "result": null
      },
      {
        "op": "split",
        "over": "corpus",
        "seconds": 0.02,
        "result": null
      },
      {
        "op": "embed",
        "over": null,
        "seconds": 0.05,
        "result": null
      },
      {
        "op": "condense",
        "over": null,
        "seconds": 0.35,
        "result": {
          "condensed": 24,
          "tokens": {
            "input": 240,
            "output": 720
          }
        }
      },
      {
        "op": "cluster",
        "over": null,
        "seconds": 8.51,
        "result": {
          "sections": 24,
          "topics": 4,
          "attached": 0,
          "collected": false
        }
      },
      {
        "op": "brief",
        "over": null,
        "seconds": 0.07,
        "result": {
          "briefed": 4,
          "skipped_pinned": 0,
          "tokens": {
            "input": 40,
            "output": 120
          }
        }
      },
      {
        "op": "build-tree",
        "over": null,
        "seconds": 0.03,
        "result": null
      },
      {
        "op": "embed",
        "over": null,
        "seconds": 0.01,
        "result": null
      }
    ]
  },
  "started_by": "admin",
  "created_at": "2026-10-03T10:08:19.907925+00:00",
  "updated_at": "2026-10-03T10:08:29.011462+00:00",
  "usage": {
    "key": "job_133cc7b3741d4852b61c305b59045264",
    "calls": 34,
    "failed": 0,
    "tokens": {
      "input": 290,
      "output": 870,
      "cache_read": 0,
      "cache_creation": 0
    },
    "model_seconds": 1.674,
    "cost": {
      "metered": {
        "usd": null,
        "unpriced": [
          "bow-64",
          "stub-text"
        ]
      },
      "subscription_estimate": {
        "usd": 0.0,
        "unpriced": []
      },
      "billing": [
        "metered"
      ]
    }
  }
}
```

```
GET /trees/default/unusable-condensations
-> 200
{
  "count": 0,
  "condensations": []
}
```

## Plant

Server stopped; 4 condensations overwritten with `Could you paste the file you would like me to condense for you?`:
- `0ba7e961dc47aa40bdf5867ec10dfe6b7d49dc03b7b19970a34dc7c1bb4073df`
- `60ecad362f5f8cf2f27770a12cc653592bd59a482813880a25d7d7bfbe6d4bc7`
- `8ee8a5bf43ff7ca691da7920e0d8a2b72715e8ea247ff8b43b6ff990ddeb15bd`
- `b2c656ad6bbb66e2d8778a8ad1d48bb2a9916e5352e16db273b9eb228d193749`

Briefs that read them (their topics and every ancestor): ['2', '3', '4', '5']

## List, then one sync

```
GET /trees/default/unusable-condensations
-> 200
{
  "count": 4,
  "condensations": [
    {
      "path": "network/network_6.py",
      "content_hash": "0ba7e961dc47aa40bdf5867ec10dfe6b7d49dc03b7b19970a34dc7c1bb4073df",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "network/network_5.py",
      "content_hash": "60ecad362f5f8cf2f27770a12cc653592bd59a482813880a25d7d7bfbe6d4bc7",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "billing/billing_7.py",
      "content_hash": "8ee8a5bf43ff7ca691da7920e0d8a2b72715e8ea247ff8b43b6ff990ddeb15bd",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "search/search_6.py",
      "content_hash": "b2c656ad6bbb66e2d8778a8ad1d48bb2a9916e5352e16db273b9eb228d193749",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    }
  ]
}
```

```
POST /trees/default/sync
-> 200
{
  "job_id": "job_656f261e894a407b947b622dd6abd733"
}
```

```
GET /jobs/job_656f261e894a407b947b622dd6abd733
-> 200
{
  "id": "job_656f261e894a407b947b622dd6abd733",
  "parent_id": null,
  "tree": "default",
  "op": "sync-tree",
  "scope": {},
  "status": "succeeded",
  "error": null,
  "result": {
    "changed": false,
    "forced": 0,
    "parked": 0,
    "judged": 0,
    "propagated": 0,
    "skipped": 0,
    "abstained": 0,
    "misfit_rate": 0.0,
    "above_baseline": false,
    "repaired": {
      "dissolved": 0,
      "split": 0,
      "migrated": 0,
      "freed": 0,
      "pinned": 0,
      "reparented": 0
    },
    "adopted": 0,
    "settle_due": false,
    "incomplete": false,
    "tree": {
      "topics_added": 0,
      "topics_removed": 0,
      "sections_refiled": 0,
      "briefs_rewritten": 0
    },
    "stages": [
      {
        "op": "update",
        "over": null,
        "seconds": 0.07,
        "result": {
          "changed": false,
          "batch": null
        }
      },
      {
        "op": "propagate",
        "over": null,
        "seconds": 0.0,
        "result": {
          "judged": 0,
          "propagated": 0,
          "skipped": 0,
          "abstained": 0,
          "incomplete": false
        }
      },
      {
        "op": "brief",
        "over": null,
        "seconds": 0.0,
        "result": {
          "briefed": 0,
          "skipped_pinned": 0
        }
      },
      {
        "op": "brief-upper",
        "over": null,
        "seconds": 0.0,
        "result": {
          "briefed": 0,
          "skipped_pinned": 0
        }
      },
      {
        "op": "monitor",
        "over": null,
        "seconds": 0.0,
        "result": {
          "measured": 4,
          "rate": 0.0,
          "baseline": 0.0,
          "above_baseline": false
        }
      },
      {
        "op": "repair",
        "over": null,
        "seconds": 0.0,
        "result": {
          "dissolved": 0,
          "split": 0,
          "migrated": 0,
          "freed": 0,
          "pinned": 0,
          "reparented": 0
        }
      },
      {
        "op": "after-repair",
        "over": null,
        "seconds": 0.0,
        "result": null
      }
    ]
  },
  "started_by": "admin",
  "created_at": "2026-10-03T10:08:29.843326+00:00",
  "updated_at": "2026-10-03T10:08:29.939658+00:00",
  "usage": null
}
```

```
GET /trees/default/unusable-condensations
-> 200
{
  "count": 4,
  "condensations": [
    {
      "path": "network/network_6.py",
      "content_hash": "0ba7e961dc47aa40bdf5867ec10dfe6b7d49dc03b7b19970a34dc7c1bb4073df",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "network/network_5.py",
      "content_hash": "60ecad362f5f8cf2f27770a12cc653592bd59a482813880a25d7d7bfbe6d4bc7",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "billing/billing_7.py",
      "content_hash": "8ee8a5bf43ff7ca691da7920e0d8a2b72715e8ea247ff8b43b6ff990ddeb15bd",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "search/search_6.py",
      "content_hash": "b2c656ad6bbb66e2d8778a8ad1d48bb2a9916e5352e16db273b9eb228d193749",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    }
  ]
}
```

```
GET /trees/default/unusable-briefs
-> 200
{
  "count": 0,
  "briefs": []
}
```

## Before/after

Condensations: 0 changed [], 24 byte-identical.

Briefs: changed [], identical ['1', '2', '3', '4', '5'], added [], removed [].

LLM calls during the sync: 0.

## Checks
- [x] list shows exactly the 4 planted
- [x] sync succeeded
- [ ] list is empty after the sync
- [ ] re-condensed exactly the 4 planted
- [ ] no re-condensation is talk-back
- [ ] rewrote exactly the briefs above them
- [ ] the sync made one call per re-condensation and rewritten brief
