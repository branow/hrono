# E007 strings: old -> new (for veto)

| where | old | new |
|---|---|---|
| Runs, Run, Home, status badge | partial | running (n/m beside it); API/CLI keep `partial` |
| Runs filter | option "partial" | removed; "running" also matches runs with stages done |
| Home stat | hold sections | topics that hold sections (tip: The others group other topics) |
| Home stat | sections filed | sections in topics |
| Home stat | sections waiting / Read, but not yet in any topic | sections waiting for a topic / Read and embedded, but not in any topic yet |
| Home tip | embeds, clusters and writes a brief | embeds them, groups them into topics and writes a brief |
| Health | N topics nothing points at | 0: Every topic can be reached from the root; 1: 1 topic is cut off from the root; n: n topics are cut off from the root |
| Health | N topics with no usable brief, or a stale one | Every topic has a brief that holds / 1 topic has no usable brief, or a stale one / n topics have ... |
| Health | N sections in no topic | No sections are waiting for a topic / 1 section is waiting ... |
| Health | N sections placed without a score | Every section was placed by a score / 1 section was placed without a score |
| Health | N runs that failed | No run has failed / 1 run has failed / n runs have failed |
| Home attention list | topics nothing points at; sections in no topic | topics cut off from the root; sections waiting for a topic |
| Map overlay | N chunks nearer | N sections nearer |
| Map legend, Guide | Did the clustering split one subject in two? | Did one subject get split across two topics? |
| Map, topic pages | 1 topics / 1 sections | 1 topic / 1 section |
| Topic page | Re-clusters what this holds | Regroups what this holds |
| Topic page | centre of the cluster | centre of the topic |
| Topic page | each of its N contents is re-filed | what it holds (N sections) is re-filed |
| Topic page | (#191) in a tooltip | removed |
| Runs tip | re-cluster | regroup the sections |
| Run page | Exactly what it returned | Raw result |
| Activity | headings lower case; judge asked per level | sentence case; judge asked once per changed topic |
| Settings | Only these are clustered into it | Only these are grouped into it |
| Failures | clustering backend | topic-grouping backend |
| Errors | node N / chunks / distinct nodes | topic N / sections / distinct topics |
