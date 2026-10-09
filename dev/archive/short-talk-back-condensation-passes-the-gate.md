# A short talk-back condensation passes the condensation gate

What: `summarize.shape.talks_back("Could you paste the file for me?")` returns
"" (usable). `unusable` returns "empty" for anything under `MIN_CHARS` (40)
before it runs the asks/addresses/talks checks, and `talks_back` turns
"empty" on non-blank text into "", so a talk-back under 40 characters is
never flagged, never listed by `GET /trees/{n}/unusable-condensations`, and
never re-condensed.

Where: src/hrono/summarize/shape.py, `unusable` / `talks_back`.

Why it matters: found while writing E001's test. A short "Could you share
the file?" is exactly what a model says to an empty or odd section, and it
then sits in the cache and every brief above it reads it as source (#221).
Fix: run the conversational checks before the length floor, or have
`talks_back` call them directly.
