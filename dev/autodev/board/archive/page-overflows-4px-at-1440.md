# Every dashboard page is 4px wider than a 1440px viewport

What: at a 1440x900 viewport `document.documentElement.scrollWidth` is 1444 on
`/ui/jobs` and `/ui/config` alike, so the page scrolls sideways by 4px. No
element's bounding box crosses the edge, so it is likely a pseudo-element or a
hidden tooltip (`.tip[data-tip]`).
Where: `src/hrono/server/templates/base.html` (shared CSS).
Why it matters: a sideways wobble on every page on a common laptop width.
Found while screenshotting E006.
