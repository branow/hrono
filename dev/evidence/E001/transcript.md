# E001 T2a: the condensation gate over a real `hrono serve`

Scratch home `/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-3/home`, its own key from `hrono admin new-key`; provider: local openai-compatible stub on :54499.

## Setup and cold build

```
POST /connections
{
  "name": "stub",
  "provider": "openai-compatible",
  "endpoint": "http://127.0.0.1:54499/v1",
  "auth": {
    "method": "none"
  }
}
-> 201
{
  "name": "stub",
  "provider": "openai-compatible",
  "endpoint": "http://127.0.0.1:54499/v1",
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
  "url": "/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-3/corpus",
  "auth": {
    "method": "none"
  }
}
-> 201
{
  "name": "corpus",
  "type": "git",
  "url": "/Users/orest/repos/hrono/.claude/worktrees/E001/.scratch/e2e-3/corpus",
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
  "job_id": "job_03eefa15cb024dc6a1a6812141d3ea70"
}
```

```
GET /jobs/job_03eefa15cb024dc6a1a6812141d3ea70
-> 200
{
  "id": "job_03eefa15cb024dc6a1a6812141d3ea70",
  "parent_id": null,
  "tree": "default",
  "op": "maintain",
  "scope": {},
  "status": "succeeded",
  "error": null,
  "result": {
    "tree": {
      "topics_added": 7,
      "topics_removed": 0,
      "sections_refiled": 0,
      "briefs_rewritten": 7
    },
    "stages": [
      {
        "op": "sync",
        "over": "corpus",
        "seconds": 0.07,
        "result": null
      },
      {
        "op": "split",
        "over": "corpus",
        "seconds": 0.03,
        "result": null
      },
      {
        "op": "embed",
        "over": null,
        "seconds": 0.09,
        "result": null
      },
      {
        "op": "condense",
        "over": null,
        "seconds": 0.63,
        "result": {
          "condensed": 48,
          "tokens": {
            "input": 480,
            "output": 1440
          }
        }
      },
      {
        "op": "cluster",
        "over": null,
        "seconds": 8.08,
        "result": {
          "sections": 48,
          "topics": 6,
          "attached": 0,
          "collected": false
        }
      },
      {
        "op": "brief",
        "over": null,
        "seconds": 0.11,
        "result": {
          "briefed": 6,
          "skipped_pinned": 0,
          "tokens": {
            "input": 60,
            "output": 180
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
  "created_at": "2026-10-03T10:12:02.160125+00:00",
  "updated_at": "2026-10-03T10:12:11.222937+00:00",
  "usage": {
    "key": "job_03eefa15cb024dc6a1a6812141d3ea70",
    "calls": 63,
    "failed": 0,
    "tokens": {
      "input": 550,
      "output": 1650,
      "cache_read": 0,
      "cache_creation": 0
    },
    "model_seconds": 2.897,
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
- `3034f77cec607243e10d94e3a6ba1c43762321b19b3a1d46251733236d806d2e`
- `4bf7c2207aca36f37df3e3fa383a851f20ddd48d1e9ec128710fa991d5438700`
- `2110d601035ca430647739573ef077bee45496ce9f2fa827b285876a87aa8d5c`
- `46f6765f8dbde9c8b7623c619b2711400851bcc7dfe3cf5da9f25cb35934ed91`

Briefs that read them (their topics and every ancestor): ['1', '2', '7']

## List, then one sync

```
GET /trees/default/unusable-condensations
-> 200
{
  "count": 4,
  "condensations": [
    {
      "path": "audit/audit_4.py",
      "content_hash": "2110d601035ca430647739573ef077bee45496ce9f2fa827b285876a87aa8d5c",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "render/render_7.py",
      "content_hash": "3034f77cec607243e10d94e3a6ba1c43762321b19b3a1d46251733236d806d2e",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "audit/audit_0.py",
      "content_hash": "46f6765f8dbde9c8b7623c619b2711400851bcc7dfe3cf5da9f25cb35934ed91",
      "why": "asks-the-caller",
      "text": "Could you paste the file you would like me to condense for you?"
    },
    {
      "path": "render/render_3.py",
      "content_hash": "4bf7c2207aca36f37df3e3fa383a851f20ddd48d1e9ec128710fa991d5438700",
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
  "job_id": "job_1eebf874be98400bbf266386c5a6e07f"
}
```

```
GET /jobs/job_1eebf874be98400bbf266386c5a6e07f
-> 200
{
  "id": "job_1eebf874be98400bbf266386c5a6e07f",
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
      "briefs_rewritten": 3
    },
    "stages": [
      {
        "op": "update",
        "over": null,
        "seconds": 0.17,
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
        "seconds": 0.03,
        "result": {
          "briefed": 2,
          "skipped_pinned": 0,
          "tokens": {
            "input": 20,
            "output": 60
          }
        }
      },
      {
        "op": "brief-upper",
        "over": null,
        "seconds": 0.01,
        "result": {
          "briefed": 1,
          "skipped_pinned": 0,
          "tokens": {
            "input": 10,
            "output": 30
          }
        }
      },
      {
        "op": "monitor",
        "over": null,
        "seconds": 0.0,
        "result": {
          "measured": 6,
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
  "created_at": "2026-10-03T10:12:11.998799+00:00",
  "updated_at": "2026-10-03T10:12:12.228258+00:00",
  "usage": {
    "key": "job_1eebf874be98400bbf266386c5a6e07f",
    "calls": 7,
    "failed": 0,
    "tokens": {
      "input": 70,
      "output": 210,
      "cache_read": 0,
      "cache_creation": 0
    },
    "model_seconds": 0.376,
    "cost": {
      "metered": {
        "usd": null,
        "unpriced": [
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

```
GET /trees/default/unusable-briefs
-> 200
{
  "count": 0,
  "briefs": []
}
```

## Before/after

Condensations: 4 changed ['2110d601035ca430647739573ef077bee45496ce9f2fa827b285876a87aa8d5c', '3034f77cec607243e10d94e3a6ba1c43762321b19b3a1d46251733236d806d2e', '46f6765f8dbde9c8b7623c619b2711400851bcc7dfe3cf5da9f25cb35934ed91', '4bf7c2207aca36f37df3e3fa383a851f20ddd48d1e9ec128710fa991d5438700'], 44 byte-identical.

Briefs: changed ['1', '2', '7'], identical ['3', '4', '5', '6'], added [], removed [].

LLM calls during the sync: 7.

## Checks
- [x] list shows exactly the 4 planted
- [x] sync succeeded
- [x] list is empty after the sync
- [x] re-condensed exactly the 4 planted
- [x] no re-condensation is talk-back
- [x] rewrote exactly the briefs above them
- [x] the sync made one call per re-condensation and rewritten brief
