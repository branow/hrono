# E066 followups (qa r1)
- A finding with an odd number of backticks shows every backtick raw, src/hrono/server/ui/__init__.py:93 (idents); pair the first n-1 backticks and leave only the stray one as text.
- Failed review run in uk reads "Помилка на review, на review of topic 18": stage and item stay English and "review" repeats, src/hrono/server/failures.py (item from summarize/review.py review_item); translate the item and drop the stage when the item names it.
- A run's Spent card shows "$0.0000" (spend still four decimals), src/hrono/usage/present.py:26; use the same cents/"<$0.01" rule as setup.dollars.
- A settle that neither placed nor reviewed (insights off, no drift) is titled "place the sections that were still waiting", src/hrono/server/ui/jobs.py (_means); say it found nothing to do.
