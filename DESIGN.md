---
name: hrono dashboard
description: The server-rendered dashboard at /ui, documented from src/hrono/server/templates/base.html.
colors:
  bg: "#F5F2EC"
  surface: "#FFFDF9"
  sunken: "#EDE8DF"
  ink: "#16212B"
  ink-soft: "#56626F"
  ink-faint: "#8A939E"
  rule: "#E1DACE"
  rule-firm: "#CFC6B7"
  accent: "#B4552D"
  accent-ink: "#FFFFFF"
  accent-wash: "#FBEDE4"
  ok: "#0F6B62"
  ok-wash: "#E3F1EE"
  warn: "#9C6F17"
  warn-wash: "#FAF0DA"
  danger: "#A32C1E"
  danger-wash: "#FBE9E5"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 640
    lineHeight: 1.2
    letterSpacing: "-.011em"
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: ".9375rem"
    fontWeight: 640
    lineHeight: 1.3
    letterSpacing: "-.011em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace"
    fontSize: ".6875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: ".07em"
  figure:
    fontFamily: "ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-.03em"
rounded:
  r1: "4px"
  r2: "7px"
  r3: "10px"
spacing:
  s1: ".25rem"
  s2: ".5rem"
  s3: ".75rem"
  s4: "1rem"
  s5: "1.5rem"
  s6: "2rem"
  s7: "3rem"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r2}"
    padding: ".35rem .7rem"
    height: "2.25rem"
  button-hover:
    backgroundColor: "{colors.sunken}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.r2}"
    padding: ".35rem .7rem"
    height: "2.25rem"
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.danger}"
    rounded: "{rounded.r2}"
  button-quiet:
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.r2}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r2}"
    padding: ".3rem .5rem"
    height: "2.25rem"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.r3}"
    padding: "{spacing.s4}"
  chip:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.label}"
    rounded: "{rounded.r1}"
    padding: ".1rem .4rem"
  chip-accent:
    backgroundColor: "{colors.accent-wash}"
    textColor: "{colors.accent}"
  tab-current:
    textColor: "{colors.accent}"
---

# Design System: hrono dashboard

## Overview

The dashboard is a working tool for an admin, a curator and a reader: warm
paper background, dark ink text, one rust accent, and monospace for every
label, figure, identifier and path. It is dense and quiet. Pages are
server-rendered Jinja with no build step, every view is a shareable URL,
and everything works from the keyboard and, where it can, without
JavaScript.

All styles live in one `<style>` block in
`src/hrono/server/templates/base.html`, as CSS custom properties on
`:root`. Page templates add only what is specific to them (the map in
`graph.html`, the run timeline in `run.html`). Words on the screen come from
`GLOSSARY.md`.

This file records the style as built. New pages reuse it. A change to the
style itself is allowed, but it goes into this file and `base.html` together,
for every page at once.

**Key Characteristics:**
- Warm neutral paper (`bg`, `surface`, `sunken`), never pure white or grey.
- One accent (rust) for links, the current tab, the primary action and focus.
- Status colors (ok, warn, danger) each come with a matching wash for backgrounds.
- Monospace for labels, chips, figures, tree names and paths; the system sans for prose.
- Flat: hairline rules and tonal steps, a 1px bottom shadow at most.
- Light and dark from one token set: the OS preference, overridden by an explicit choice.

## Colors

A warm, low-chroma paper and ink palette with one saturated accent and three
status hues. Every color is a `:root` token with a dark-theme value; a page
never writes a raw hex.

### Primary
- **Rust** (accent): links, the current tab's text and underline, the
  primary button, focus outlines, checkbox fill, the brand mark.
- **Rust Wash** (accent-wash): search-hit `mark` backgrounds and the accent chip.

### Neutral
- **Paper** (bg): the page background.
- **Card White** (surface): cards, the top bar, inputs, menus.
- **Sunken Paper** (sunken): hover rows, card footers, default chips, preview blocks.
- **Ink** (ink), **Soft Ink** (ink-soft), **Faint Ink** (ink-faint): text
  at three strengths: content, secondary text and hints, metadata and table heads.
- **Hairline** (rule) and **Firm Rule** (rule-firm): dividers inside cards;
  control borders and table head underlines.

### Status
- **Teal** (ok / ok-wash), **Ochre** (warn / warn-wash), **Brick** (danger /
  danger-wash): chips, callouts, diff lines and the danger button. The text
  takes the hue and the background takes its wash.

### Named Rules
**The One Accent Rule.** Rust marks where you are and what to do next.
It is never decoration, never a status, and one screen has one primary button.

**The Token-Only Rule.** Colors come from `var(--token)`. A new color is a new
token with both a light and a dark value, added to `base.html`.

## Typography

**Body Font:** the system sans stack (`system-ui`, `-apple-system`, Segoe UI, Roboto)
**Label/Mono Font:** the system mono stack (`ui-monospace`, SF Mono, Menlo, Consolas)

**Character:** plain system faces at a small working size (14px body), with
weight doing the work of size. Monospace carries anything that is data
rather than prose.

### Hierarchy
- **Headline** (640, 1.5rem, 1.2): the page title (`h1`), once per page.
- **Title** (640, .9375rem, 1.3): card and section heads (`h2`); `h3` is .875rem.
- **Body** (400, 14px, 1.55): prose and table cells; hints are .8125rem
  in Soft Ink, capped at 72ch.
- **Label** (mono 600, .6875rem, .07–.1em tracking, uppercase): table
  heads, the page eyebrow, the tree picker's key.
- **Figure** (mono 600, 1.75rem, tabular numbers): stat tiles.

### Named Rules
**The Data-Is-Mono Rule.** Tree names, ids, paths, counts in chips and stat
figures are monospace with tabular numbers; sentences are never mono.

## Layout

Content sits in a centred `main` of at most 1180px with 1.5rem padding, under
a full-width top bar. Spacing uses the `s1`–`s7` scale (.25rem to 3rem);
stacks and grids use `s4` gaps. Card pairs use an auto-fit grid
(`minmax(310px, 1fr)`) and stat tiles `minmax(150px, 1fr)`. Below 1080px the
tabs move to their own scrollable row and never wrap. Below 40rem, wide
tables drop their least-needed columns. The page never scrolls sideways;
`tests/server/test_ui_browser.py` checks this in Chromium.

Every control is the same height (2.25rem; small 1.875rem; search 2.5rem),
so an input and the button beside it line up.

## Elevation & Depth

The style is flat. Depth comes from tonal steps (sunken < bg < surface) and
hairline borders. The only resting shadow is `--shadow` (a 1px bottom line,
`0 1px 0 #16212b08`) on cards and stat tiles. Floating layers (the tree
menu, the tip box) use `var(--shadow-lift)`, but no theme defines that
token yet, so they have no shadow. Define it before relying on it.

**The Flat-By-Default Rule.** A surface is separated from the page by its
border and its tone, not by a shadow.

## Shapes

Gently rounded and consistent: 4px (`r1`) for chips, menu items and focus
rings; 7px (`r2`) for buttons, inputs, menus and callouts; 10px (`r3`) for
cards and stat tiles. Info marks (`.tip`) are the only circles. Callouts
carry a 3px left border in their status hue.

## Components

### Buttons
- **Shape:** 7px radius, 1px Firm Rule border, 560 weight, 2.25rem tall.
- **Default:** Card White background, Ink text; hover is Sunken Paper; on press it moves down half a pixel.
- **Primary:** Rust fill with white text; hover brightens it.
- **Danger:** Brick border and text on Card White; hover is the Brick wash.
- **Quiet:** no border and no fill, Soft Ink text; for secondary actions in rows.
- **Disabled:** 50% opacity, not-allowed cursor.

### Chips
- **Style:** mono 560 .75rem on Sunken Paper with a 4px radius.
- **Variants:** `accent`, `ok`, `warn`, `danger` (hue text on its wash), and
  `plain` (text only).

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** Card White with a Hairline border and the flat shadow.
- **Parts:** a head (`s3 s4 0`), a body (`s4`), and an optional footer on
  Sunken Paper above a hairline.

### Inputs / Fields
- **Style:** Card White, Firm Rule border, 7px radius, 400 weight even inside a bold label.
- **Select:** a custom drawn chevron replaces the native arrow.
- **Focus:** a 2px Rust outline offset 2px, on every focusable element.

### Navigation
- **Top bar:** Card White with a Firm Rule bottom border; the brand, the tree
  picker, the tabs, the finder and who is signed in.
- **Tabs:** Soft Ink, 520 weight; the current tab is Rust, 640, with a 2px Rust underline.
- **Tree picker:** a `<details>` menu of links that works without JavaScript;
  with one tree it shows the name and offers no choice.
- **Skip link:** first in tab order, shown only on focus.

### Tables
Mono uppercase Faint Ink heads over a Firm Rule; rows divided by Hairlines,
with counts right-aligned in tabular numbers and dates in mono.

### Callouts and empty states
A callout is a bordered row with a status-hued left edge and title. An empty
state is a centered title and hint, with a faint mark above.

### Tip marks
A small circled mark beside a term. Its explanation appears at once on hover
and on keyboard focus, in a box script places inside the viewport. Use this
instead of `title=`.

## Do's and Don'ts

### Do:
- **Do** take every color, radius and space from the `:root` tokens in `base.html`.
- **Do** keep one primary (Rust) action per screen and make the main action stand out.
- **Do** set data (names, ids, paths, figures) in mono with tabular numbers.
- **Do** keep labels short and metadata quiet (Faint Ink, small).
- **Do** make every view a URL, reachable from the keyboard, readable in light and dark.
- **Do** verify laid-out pixels (overflow, wrapping, overlap) in a real browser test.

### Don't:
- **Don't** add a raw hex, a new font or a framework; there is no frontend build.
- **Don't** use `title=` tooltips; use a tip mark.
- **Don't** repeat the tree's name on a page that already shows it in the picker.
- **Don't** let a row of tabs or controls wrap raggedly or scroll the page sideways.
- **Don't** use words outside `GLOSSARY.md` on the screen.
