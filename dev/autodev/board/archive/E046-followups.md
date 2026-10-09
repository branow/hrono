# E046 followups (qa round 1, head 26545ae)

- Commits: 461 and 462 landed as one commit (26545ae); CONTRIBUTING asks for one Conventional Commit per ticket. Process note for dev, nothing to change in code.
- The "Find a topic" filter hides options, but a level whose options are all hidden still shows its empty optgroup label (src/hrono/server/templates/config.html:94-100). Fix: also hide an optgroup once none of its options are left visible.
- The filter can hide the option that is currently selected, and the select keeps showing it (src/hrono/server/templates/config.html:94-100). Fix: when the selected option gets hidden, reset the select to "pick a topic" or to the first visible match.
- The topic-filter JS has no automated test; test_the_topic_picker_groups_topics_by_level_and_offers_a_filter only checks the box renders (tests/server/test_ui_settings.py:1351). qa drove it in Chromium. Fix: add a browser-level check if a playwright harness lands, or else leave it.
