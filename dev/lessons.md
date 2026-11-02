# hrono project lessons (read by every autodev agent; retro appends)
- dev, prompts: when a shipped prompt default changes, add every earlier shipped default hash to the upgrade list and test an old row is replaced while an edited one is kept; E055 shipped without it and qa had to add 10 hashes (e4dc224).
- dev, tests: for each line of prompt or wiring a feature depends on, remove it and see a test fail; E055 qa found the "areas" line for level 2+ could be deleted with the suite green (68b66e4).
