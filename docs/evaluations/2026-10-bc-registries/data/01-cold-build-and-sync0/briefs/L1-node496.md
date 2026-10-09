<!-- level 1, node 496, children [197, 198] -->

**Parent brief: closing `<script>` include block of a SchemaSpy-style database documentation page**

This is pure library-loading boilerplate with no logic of its own. It sits just before `</body></html>`. It loads about 18–20 scripts from a relative `../bower/` (bower_components) directory, then two local scripts. Every child restates the same inventory, with differing detail.

**Inventory, in load order**
- **Core UI:** jQuery 2.2.3, jQuery UI, Bootstrap 3.3.5.
- **Tables and export:**
  - DataTables: `dataTables.net`, `net-bs` (the Bootstrap 3 theme), `buttons`, `buttons-bs`, `buttons.html5`, `buttons.print` and `buttons.colVis`.
  - SheetJS (`xlsx.full.min.js`).
  - pdfmake (`pdfmake.min.js`) plus `vfs_fonts.js`.
- **AdminLTE ecosystem:** `jquery.slimscroll.min.js`, `fastclick.js` and `admin-lte/dist/js/app.min.js`.
- **Layout and navigation helpers:** Salvattore (`salvattore.min.js`, masonry layout) and AnchorJS (`anchor.min.js`).
- **SQL display:** `codemirror.js`, then `codemirror/sql.js`.
- **Local scripts:** `table.js`, then `schemaSpy.js`. A couple of children call the first one `column.js` or `main.js`, which is most likely summarizer drift.
- Two children give script counts ("seven", "10"). Both are lower than the number of files they list, so ignore them.

**Load-order constraints**
- Plugins load first, then the AdminLTE `app.js`, then the app-specific scripts (`table.js`, `schemaSpy.js`).
- The DataTables buttons plugins need `dataTables.net` loaded first.
- `sql.js` must load after `codemirror.js`.
- One child says CodeMirror must load before AdminLTE's `app.js`.
- pdfmake needs `vfs_fonts.js` as well as `pdfmake.min.js`, or the embedded fonts won't render.

**Risks and caveats**
- **Dated stack:** jQuery 2.2.3 (~2016) and Bootstrap 3.3.5 (~2015) are end-of-life. Bower is deprecated, so consider migrating to npm or yarn.
- **Hard dependencies:** The page depends heavily on AdminLTE, and no bundling is visible.
- **Fragile paths:** All paths are relative (`../bower/...`). Moving the folder or changing the HTML's directory depth breaks every include.
- **No integrity or pinning:** There are no integrity hashes or version pins, so you can't tell whether the frozen components are out of date.
- **Obsolete polyfills:** SlimScroll and FastClick are largely native in modern browsers, so check whether any ordering dependency on them is real.
- **Undefined local code:** `table.js` and `schemaSpy.js` aren't defined in the snippet. They must exist in the project, or the page may fail silently.
- **Export formats:** Print, xlsx and pdf are all available, but no conflict handling is shown.
- **Possible truncation:** The snippet ends in `</body></html>` with no visible opening tag, so it may be incomplete.
