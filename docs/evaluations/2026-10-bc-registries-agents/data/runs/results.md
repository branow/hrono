# Results: agents with and without hrono on BC Registries

## locate (40 questions, paired)

| Metric | repo | hrono | hrono - repo [95% CI] | Wilcoxon p |
|---|---|---|---|---|
| recall | 0.768 [0.699, 0.830] | 0.780 [0.719, 0.838] | 0.012 [-0.022, 0.047] | 0.447 |
| precision | 0.681 [0.610, 0.750] | 0.697 [0.635, 0.761] | 0.016 [-0.027, 0.063] | 0.614 |
| f1 | 0.708 [0.643, 0.768] | 0.720 [0.666, 0.773] | 0.012 [-0.017, 0.043] | 0.638 |
| turns | 12 [10, 15] | 10 [9, 11] | -2 [-4, -1] | 0.00743 |
| wall s | 20 [17, 23] | 26 [23, 29] | 6 [4, 7] | 2.72e-06 |
| output tokens | 2,262 [1,874, 2,682] | 2,107 [1,824, 2,404] | -156 [-369, 51] | 0.519 |
| context read (tokens) | 152,073 [127,169, 180,167] | 183,173 [157,337, 210,174] | 31,100 [14,981, 47,100] | 0.000336 |
| API-equiv. $ | 0.099 [0.086, 0.114] | 0.113 [0.101, 0.125] | 0.014 [0.005, 0.023] | 0.00666 |

recall: hrono better on 6, worse on 5, tied on 29.
hrono arm: recall calls per question 1.0, tree files opened per question 0.5 (questions that opened any: 18).

recall by repo:

| repo | n | repo | hrono |
|---|---|---|---|
| business-filings-ui | 4 | 0.636 | 0.614 |
| lear | 14 | 0.813 | 0.818 |
| sbc-auth | 11 | 0.722 | 0.786 |
| sbc-pay | 11 | 0.805 | 0.787 |

## arch (36 questions, paired)

| Metric | repo | hrono | hrono - repo [95% CI] | Wilcoxon p |
|---|---|---|---|---|
| coverage | 0.692 [0.643, 0.739] | 0.649 [0.608, 0.690] | -0.043 [-0.088, 0.004] | 0.0564 |
| errors | 0.111 [0.028, 0.222] | 0.139 [0.028, 0.250] | 0.028 [-0.111, 0.167] | 0.705 |
| turns | 12 [11, 14] | 8 [7, 9] | -4 [-6, -3] | 4.59e-05 |
| wall s | 25 [23, 27] | 27 [26, 28] | 2 [0, 3] | 0.0218 |
| output tokens | 3,422 [3,154, 3,714] | 2,841 [2,677, 3,026] | -581 [-832, -331] | 7.81e-05 |
| context read (tokens) | 135,588 [119,440, 152,902] | 140,511 [128,374, 152,543] | 4,924 [-13,735, 22,588] | 0.441 |
| API-equiv. $ | 0.134 [0.121, 0.147] | 0.121 [0.114, 0.128] | -0.013 [-0.026, 0.000] | 0.0743 |

coverage: hrono better on 7, worse on 19, tied on 10.
hrono arm: recall calls per question 1.0, tree files opened per question 1.0 (questions that opened any: 36).

coverage by kind:

| kind | n | repo | hrono |
|---|---|---|---|
| change | 10 | 0.681 | 0.686 |
| concept | 12 | 0.715 | 0.670 |
| flow | 14 | 0.680 | 0.606 |

coverage by area:

| area | n | repo | hrono |
|---|---|---|---|
| auth | 6 | 0.732 | 0.694 |
| cross | 6 | 0.689 | 0.655 |
| lear-async | 6 | 0.732 | 0.631 |
| lear-filings | 6 | 0.641 | 0.645 |
| pay | 6 | 0.667 | 0.597 |
| ui | 6 | 0.691 | 0.673 |

## arch, all arms (unpaired summary)

| Arm | n | Fact coverage [95% CI] | Errors | Turns | Recall calls | Brief reads | API-equiv. $ |
|---|---|---|---|---|---|---|---|
| none | 36 | 0.398 [0.355, 0.440] | 1.36 | 1.0 | 0.0 | 0.0 | 0.000 |
| tree | 36 | 0.498 [0.453, 0.541] | 0.44 | 6.6 | 4.9 | 0.3 | 0.111 |
| hrono | 36 | 0.649 [0.608, 0.690] | 0.14 | 7.9 | 1.0 | 1.0 | 0.121 |
| repo | 36 | 0.692 [0.643, 0.738] | 0.11 | 12.2 | 0.0 | 0.0 | 0.134 |
