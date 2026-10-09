<!-- level 1, node 496, children [66, 96, 118, 164, 165, 198, 259, 262, 277, 351, 352, 356, 357] -->

# Parent brief: AdminLTE dashboard front-end stack (CSS, JS, vendored libraries)

These notes describe the static front-end assets of an AdminLTE v2.3.x (Bootstrap 3) admin dashboard. That includes a SchemaSpy-style HTML page that loads the same stack from `../bower/`. Almost all the child notes were duplicated, and the truncated sources mean many rules and functions are incomplete.

## 1. AdminLTE theme and CSS
- **Core stylesheets (v2.3.5 and v2.3.8, MIT, Almsaeed Studio)**
  - Layout: `.wrapper`, `.content-wrapper`, and `.main-sidebar` (230px, z-index 810). The sidebar collapses by translate at ≥768px and drops its margin at ≤767px. `.sidebar-mini` collapses to 50px.
  - Right-hand control sidebar: 230px wide, z-index 1010, with dark and light themes.
  - Components: navbar, forms, progress bars, small-box, box, timeline, buttons, direct-chat, callouts, mailbox, lock screen, login/register, error pages, invoice and profile, social buttons, and a 15-color palette.
  - Bundled third-party styles: a calendar plugin and a Salvattore masonry grid.
- **Color skins (`.skin-*`)**
  - Dark-sidebar skins: blue, green, red, yellow, purple and black.
  - Light-sidebar skins: `-light` variants of the same six.
  - Shared structure: sidebar `#222d32` (dark) or `#f9fafc` (light), plus hover, active and submenu colors, a sidebar search form, and mobile/desktop media queries (767px/768px).
  - Skin colors: blue navbar `#3c8dbc`, green `#00a65a`, red `#dd4b39`, yellow `#f39c12`, purple `#605ca8`, black white-navbar.
- **Stray Bootstrap CSS fragment**
  - Covers navbar-default/inverse, pagination, labels and badges. It is unrelated to the skins and is truncated.

## 2. AdminLTE JavaScript (v2.3.8)
- **`$.AdminLTE.options`** is the central config: feature toggles, selectors, `animationSpeed` 500, `screenSizes` and a 16-color palette. On DOM ready, `_init()` activates the modules.
- **Modules:** `layout`, `pushMenu`, `tree`, `controlSidebar`, `boxWidget`, `boxRefresh`, `activateBox`/`toggleBox`/`removeBox`, `todolist` and `directChat`.
- **Demo-only skin and layout switcher**
  - It uses `localStorage` and `data-skin` attributes to change the skin and layout.
  - There is also a separate skin-selector widget with 12 hardcoded skin classes (6 colors × light/dark).
- **Dashboard scripts:** an init script wires up sparkline, Morris.js, knob, vector map, datepicker and WYSIHTML5. A second script sets up Chart.js line and doughnut charts, a 26-marker world map and sparklines driven by data attributes. All chart data is static demo data.
- **Page script block:** the closing `<script>` block of the SchemaSpy-style page loads 20+ scripts from `../bower/`. Those are jQuery 2.2.3, jQuery UI, Bootstrap 3.3.5, DataTables (with buttons and export), SheetJS, pdfmake, SlimScroll, FastClick, Salvattore, AnchorJS, CodeMirror (with SQL), AdminLTE `app.min.js`, and the local `table.js` and `schemaSpy.js`.

## 3. Third-party libraries (vendored)
- **Bootstrap 3.3.5 and 3.3.7 JS plugins**
  - Plugins: transition, alert, button, carousel, collapse, dropdown, modal, tooltip, popover, scrollspy, tab and affix.
  - They use the `+function($)` IIFE pattern and the data-API.
  - A Grunt-generated CommonJS bundle requires all 11 modules.
- **jQuery 3.2.1 core and Sizzle 2.3.3**
  - Core: setup, utilities, data, ready, events, DOM building, attributes, CSS, animation, and offset and dimensions.
  - Selector engine: tokenize/compile/select, pseudo-selectors, caches and sort.
  - Also: the UMD wrapper, which needs `require("jquery")(window)` under Node.
- **jQuery UI 1.11.4**
  - Core: widget factory, mouse, position, keyCode and the effects core.
  - Widgets: accordion, autocomplete, button, datepicker, dialog, menu, progressbar, selectmenu, slider, spinner, tabs and tooltip.
  - Interactions: draggable, droppable, resizable, selectable and sortable.
  - Support: the ddmanager and the jQuery.Color plugin. The effect modules include blind, bounce and fold.
- **FastClick:** removes the 300ms touch delay, with device detection that skips it when it isn't needed. The touch lifecycle handlers are `onTouchStart`, `onTouchMove`, `onTouchEnd` and `onTouchCancel`. It uses `onMouse`/`onClick` ghost-click blocking and a `destroy()` method.
- **slimScroll 1.3.8 (Piotr Rochala, MIT/GPL):** a custom scrollbar with a rail and bar, drag, wheel and touch support, and show/hide timers.

## Cautions

**Truncated or incomplete sources**
- Several snippets are cut off mid-selector or mid-function, including the `.skin-black` and `.skin-green` rules, the Bootstrap fragment, and the dropdown/modal file boundary. The truncated parts include `_init()`, `setDocument`, the palette gradients and the slimScroll init.
- It is unclear whether the HTML script block is complete.

**Known bugs and typos**
- The option is misspelled `enableBSToppltip`.
- Skins define `.sidebar-toggle` hover twice, and the second rule wins, which is probably a copy-paste error.
- jQuery UI `size` effect: `factor.to.y` is probably used twice.
- jQuery UI Resizable: `outerDimensions` is cached inside a loop, and the source comment suggests that is a bug.
- `controlSidebar._fix()`: `hasBindedResize` is never reset.
- `boxRefresh` with an empty `source` returns silently, though other notes say it logs a console error.

**Maintainability and compatibility**
- Colors are hardcoded everywhere in the CSS, with no variables.
- The vendor prefixes are outdated.
- The legacy IE and old-WebKit hacks are fragile to remove.
- The versions are old (jQuery 2.2.3, Bootstrap 3.3.5/3.3.7, jQuery UI 1.11.4), and Bootstrap 3.3.7 is unmaintained.
- The Bootstrap bundle is autogenerated, so regenerate it with Grunt instead of editing it.
- SlimScroll and FastClick are largely native in modern browsers now.

**Dependencies and load order**
- All paths are relative to `../bower/`, so moving the folder breaks every include.
- Plugins load first, then AdminLTE, then the app scripts. DataTables buttons need `dataTables.net` first, and CodeMirror's `sql.js` needs `codemirror.js` first.
- Optional plugins (slimScroll, FastClick, iCheck) are skipped silently when missing.
- slimScroll's `railDraggable` needs jQuery UI Draggable.
- `table.js` and `schemaSpy.js` are not shown, so they must exist.

**Library gotchas (selected)**
- Widget factory: `_super` is volatile, and redefining a parent widget redefines its children recursively.
- Datepicker: it is a singleton with global state, so only one picker is active at a time. Two-digit years pivot around a cutoff of about 30.
- Tooltip: the `closing` flag must be set before `_hide()` to avoid an infinite loop.
- Dialog: all modals share one document-level `focusin` handler.
- FastClick: a touch identifier of 0 in Chrome devtools emulation is silently ignored.
- jQuery: `extend()` deep copy silently skips circular references, and `isNumeric("-0x10")` returns true.
- jQuery events: `focus`/`blur` use `delegateType` to route to `focusin`/`focusout`.
- Skin switcher: HTML is built by unescaped string concatenation, so dynamic skin names are an injection risk.
- Chart.js: the doughnut `percentageInnerCutout=50` gives a hollow center. The sparklines render empty without their HTML data attributes.
