## Results


### Single-shot retrieval + answer, all questions

| System | n | Score /100 [95% CI] | Correctness | Completeness | Relevance | Clarity | Reasoning | File recall | Context chars |
|---|---|---|---|---|---|---|---|---|---|
| closed-book | 144 | **70.1** [67.4, 72.6] | 13.1 | 12.5 | 14.6 | 16.1 | 13.9 | – | 0 |
| bm25 | 144 | **65.7** [62.8, 68.4] | 12.3 | 11.3 | 13.7 | 15.5 | 13.0 | 0.69 (n=88) | 7981 |
| dense | 144 | **67.5** [64.9, 70.0] | 12.8 | 11.8 | 13.8 | 15.7 | 13.4 | 0.75 (n=88) | 7975 |
| raptor | 144 | **67.2** [64.6, 69.5] | 12.6 | 11.7 | 14.0 | 15.5 | 13.3 | 0.70 (n=88) | 7983 |
| hrono | 144 | **67.5** [65.0, 69.9] | 12.8 | 11.7 | 14.0 | 15.8 | 13.3 | 0.59 (n=88) | 4170 |

Paired against **hrono** (positive = hrono better):

| vs | n pairs | Mean diff [95% CI] | Wins / ties / losses | Wilcoxon p | Holm p |
|---|---|---|---|---|---|
| closed-book | 144 | -2.6 [-5.1, +0.1] | 49 / 9 / 86 | 0.000608 | 0.00243 |
| bm25 | 144 | +1.9 [-0.2, +4.0] | 79 / 9 / 56 | 0.0853 | 0.256 |
| dense | 144 | -0.0 [-2.1, +2.2] | 68 / 6 / 70 | 0.97 | 1 |
| raptor | 144 | +0.4 [-1.7, +2.5] | 77 / 4 / 63 | 0.623 | 1 |

### Score by repository (mean /100)

| System | flask | requests | streamlink |
|---|---|---|---|
| closed-book | 76.6 (n=48) | 78.9 (n=48) | 54.7 (n=48) |
| bm25 | 67.3 (n=48) | 73.0 (n=48) | 56.6 (n=48) |
| dense | 68.7 (n=48) | 73.5 (n=48) | 60.4 (n=48) |
| raptor | 65.9 (n=48) | 72.5 (n=48) | 63.0 (n=48) |
| hrono | 67.7 (n=48) | 73.1 (n=48) | 61.8 (n=48) |
| agent-repo | 81.2 (n=16) | 81.8 (n=16) | 70.8 (n=16) |
| agent-hrono | 79.6 (n=16) | 79.7 (n=16) | 72.9 (n=16) |
| agent-hrono-first | 79.1 (n=16) | 81.0 (n=16) | 73.9 (n=16) |

### hrono recall hit counts

- questions: 144; zero hits: 21 (15%); mean hits 5.4; median 5
- hrono score when recall returned nothing: 67.4 (n=21); when it returned passages: 67.6 (n=123)

### Agent subset (48 questions), every system

| System | n | Score /100 [95% CI] | Correctness | Completeness | Relevance | Clarity | Reasoning | File recall | Context chars |
|---|---|---|---|---|---|---|---|---|---|
| closed-book | 48 | **72.2** [67.8, 76.2] | 13.8 | 13.0 | 15.0 | 16.2 | 14.3 | – | 0 |
| bm25 | 48 | **67.5** [62.6, 72.0] | 12.7 | 11.6 | 14.1 | 15.9 | 13.3 | 0.71 (n=32) | 7976 |
| dense | 48 | **69.8** [65.5, 73.8] | 13.3 | 12.4 | 14.3 | 16.0 | 13.8 | 0.76 (n=32) | 7973 |
| raptor | 48 | **70.5** [66.7, 73.9] | 13.4 | 12.3 | 14.7 | 16.0 | 14.0 | 0.66 (n=32) | 7982 |
| hrono | 48 | **67.5** [63.5, 71.2] | 12.7 | 11.5 | 14.1 | 15.9 | 13.3 | 0.54 (n=32) | 3810 |
| agent-repo | 48 | **78.0** [74.3, 81.1] | 15.4 | 14.6 | 15.6 | 16.9 | 15.5 | – | 0 |
| agent-hrono | 48 | **77.4** [74.3, 80.0] | 15.2 | 14.3 | 15.8 | 16.7 | 15.4 | – | 0 |
| agent-hrono-first | 48 | **78.0** [74.7, 80.6] | 15.4 | 14.6 | 15.7 | 16.8 | 15.5 | – | 0 |

Paired against **agent-repo** (positive = agent-repo better):

| vs | n pairs | Mean diff [95% CI] | Wins / ties / losses | Wilcoxon p | Holm p |
|---|---|---|---|---|---|
| closed-book | 48 | +5.7 [+2.7, +9.3] | 33 / 5 / 10 | 0.000249 | 0.000747 |
| bm25 | 48 | +10.4 [+6.7, +14.4] | 36 / 3 / 9 | 4.67e-06 | 2.8e-05 |
| dense | 48 | +8.1 [+4.4, +12.0] | 37 / 4 / 7 | 3.87e-05 | 0.000155 |
| raptor | 48 | +7.5 [+4.0, +10.9] | 38 / 2 / 8 | 1.62e-05 | 8.1e-05 |
| hrono | 48 | +10.4 [+7.0, +13.9] | 38 / 2 / 8 | 2.05e-06 | 1.43e-05 |
| agent-hrono | 48 | +0.6 [-1.8, +2.4] | 25 / 5 / 18 | 0.0893 | 0.179 |
| agent-hrono-first | 48 | -0.0 [-2.4, +1.7] | 25 / 5 / 18 | 0.188 | 0.188 |

### Agent effort per question

| Arm | n | Turns (mean) | Wall s (mean) | Output tokens (mean) | Cache read (mean) | API-equiv. $ (mean) | Hit max turns |
|---|---|---|---|---|---|---|---|
| agent-repo | 48 | 3.9 | 11 | 1124 | 37147 | 0.035 | 0 |
| agent-hrono | 48 | 3.7 | 11 | 1070 | 39219 | 0.037 | 0 |
| agent-hrono-first | 48 | 3.6 | 15 | 1034 | 37876 | 0.047 | 0 |

### LLM calls by role (benchmark harness)

| Role | Calls | Input | Output | Cache read | Cache write | Model seconds | API-equiv. $ |
|---|---|---|---|---|---|---|---|
| agent:agent-hrono | 65 | 382 | 66898 | 2426504 | 308625 | 693 | 2.39 |
| agent:agent-hrono-first | 48 | 280 | 49635 | 1818054 | 349275 | 715 | 2.26 |
| agent:agent-repo | 69 | 422 | 74530 | 2401900 | 293093 | 736 | 2.40 |
| answer:bm25 | 144 | 288 | 122897 | 0 | 499672 | 1200 | 3.23 |
| answer:closed-book | 180 | 428 | 226861 | 868877 | 180951 | 2040 | 3.17 |
| answer:dense | 143 | 286 | 122570 | 0 | 511156 | 1195 | 3.27 |
| answer:hrono | 192 | 384 | 162741 | 478880 | 619180 | 1645 | 4.20 |
| answer:raptor | 191 | 382 | 154395 | 480192 | 842504 | 1670 | 5.01 |
| judge | 894 | 1788 | 37010 | 0 | 3251389 | 2866 | 13.38 |
| lightrag | 85 | 163546 | 920531 | 295776 | 75555 | 6490 | 4.95 |
| raptor-summary | 1318 | 2636 | 566410 | 4881505 | 4770568 | 7133 | 25.73 |
| smoke | 1 | 10 | 51 | 11410 | 3288 | 3 | 0.01 |

### hrono build (from hrono's own ledger)

| Role | Calls | Input | Output | Cache read | Model seconds |
|---|---|---|---|---|---|
| brief | 74 | 148 | 190851 | 743478 | 1344 |
| brief-upper | 9 | 18 | 46131 | 90423 | 280 |
| condense | 207 | 2061 | 588427 | 2394783 | 6527 |
| validate | 4 | 24 | 332 | 28458 | 12 |
