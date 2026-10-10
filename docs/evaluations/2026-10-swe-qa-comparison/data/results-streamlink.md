
### streamlink only (least memorized), single-shot

| System | n | Score /100 [95% CI] | Correctness | Completeness | Relevance | Clarity | Reasoning | File recall | Context chars |
|---|---|---|---|---|---|---|---|---|---|
| closed-book | 48 | **54.7** [49.7, 59.5] | 9.1 | 9.0 | 11.5 | 14.3 | 10.7 | – | 0 |
| bm25 | 48 | **56.6** [51.1, 62.3] | 9.9 | 9.5 | 11.4 | 14.6 | 11.2 | 0.00 (n=1) | 7992 |
| dense | 48 | **60.4** [55.0, 65.5] | 10.8 | 10.8 | 12.0 | 14.9 | 11.9 | 0.00 (n=1) | 7975 |
| raptor | 48 | **63.0** [58.3, 67.5] | 11.5 | 11.5 | 12.6 | 14.9 | 12.4 | 0.00 (n=1) | 7975 |
| hrono | 48 | **61.8** [57.0, 66.5] | 11.2 | 10.9 | 12.5 | 15.1 | 12.1 | 0.00 (n=1) | 4786 |

Paired against **hrono** (positive = hrono better):

| vs | n pairs | Mean diff [95% CI] | Wins / ties / losses | Wilcoxon p | Holm p |
|---|---|---|---|---|---|
| closed-book | 48 | +7.1 [+1.6, +13.0] | 30 / 4 / 14 | 0.0159 | 0.0635 |
| bm25 | 48 | +5.2 [+0.8, +9.8] | 31 / 2 / 15 | 0.0174 | 0.0635 |
| dense | 48 | +1.5 [-2.7, +5.8] | 23 / 1 / 24 | 0.586 | 1 |
| raptor | 48 | -1.2 [-5.0, +2.8] | 25 / 0 / 23 | 0.64 | 1 |
