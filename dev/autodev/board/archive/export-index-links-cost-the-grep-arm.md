# the index links cost the grep arm 24%

From E022 review. Section links on index pages cut the walk 1,007k -> 827k
tokens but raised grep 374k -> 464k (root.md 5.0 -> 9.5 KB, carried every
turn). Walk is still 2x raw (410k). Ideas: a lighter entry per link (path
only), or links only on pages below root. Measure both arms with
`.e2e/eval/run.py`; baseline evidence/E022/head/.
