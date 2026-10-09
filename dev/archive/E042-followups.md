# E042 followups (minor, from qa round 1)

- The "Agent questions" card touches the "Each person" card above it: `mt-4` is not a defined class and the section sits outside the page's `.stack` - src/hrono/server/templates/usage.html:116 - move the section inside the `.stack` div (or use a spacing class that exists).
- The header chips "N calls" and "X% not confident" sum only the last 30 days but read as totals, and the `[-DAYS:]` window is untested (mutating it to `[:DAYS]` survives) - src/hrono/server/ui/usage.py:61 - label the chips as the last 30 days and add a test with more than 30 days of rows.
- The Ask link is rebuilt by hand, duplicating `ask._link` - src/hrono/server/ui/usage.py:70 - call the Ask page's link builder instead.
- Two `# type: ignore[call-overload]` on the day sums - src/hrono/server/ui/usage.py:62-63 - have `recall_log.per_day` return typed rows (TypedDict or a dataclass) so the sums need no ignore.
