# forced settle: what survived the partial run

node ids (were [1,2,3,4,5,6,7] before settle): [1, 2, 4, 5, 8, 9, 10]
members: [(1, 12), (2, 13), (4, 15), (5, 12), (8, 13), (9, 19), (10, 10)]
coords: 94
briefs: 7

brief provenance (created_at shows which were regenerated):
  node 1: 17:13:04 813B haiku
  node 2: 17:13:21 4060B haiku
  node 4: 17:13:56 3069B haiku
  node 5: 17:53:43 3143B haiku
  node 8: 17:54:04 2991B haiku
  node 9: 17:54:22 3111B haiku
  node 10: 17:54:43 4582B haiku

signatures:
  node 1: c00cfbd45ff9d980
  node 2: 9cd746f336ab2138
  node 4: 60b816b97200b603
  node 5: 3c850bca2775f757
  node 8: 152245fa5d1499b5
  node 9: 5b118adb3125f20d
  node 10: 67f30521cd86388d

pending: [('docs/unrelated-cooking-notes.md', 1), ('source/util-helpers.js', 4)]
