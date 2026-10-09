<!-- level 1, node 497, children [65, 86, 97, 98, 99, 103, 121, 122, 136, 137, 138, 141, 142, 166, 167, 174, 197, 263] -->

# Parent brief: front-end asset stack and generated documentation (DataTables, icon fonts, SchemaSpy)

The group covers two kinds of material: **vendored front-end libraries and fonts** (circa 2014–2016), and **SchemaSpy 6.0.0 HTML documentation pages** for PostgreSQL databases ("postgres" and "auth"). Nearly all notes are duplicated. Most of the legacy stack is end-of-life.

## 1. Icon fonts and web fonts
- **Ionicons v2.0.0** (MIT).
  - `@font-face "Ionicons"` loads eot, ttf, woff and svg, each with `?v=2.0.0`. The SVG URL needs its `#Ionicons` fragment.
  - One shared base rule covers 800+ `.ion-*` classes: inline-block, `font-family: "Ionicons"`, `speak: none`, antialiased.
  - Mappings follow `.ion-NAME:before { content: "\fXXX" }`, from about `\f101` to `\f4dd`+. Examples: `ion-alert` `\f101`, `ion-android-add` `\f2c7`, `ion-world` `\f4d3`. They include iOS filled, `-empty` and `-outline` variants plus brand icons.
- **Font Awesome 4.7.0** (font under OFL, CSS under MIT).
  - `@font-face 'FontAwesome'` loads eot, woff2, woff, ttf and svg.
  - Utilities: sizes (`fa-lg`, `fa-2x`–`fa-5x`), `fa-fw`, `fa-ul`, pull, border, spin and pulse animation, rotate and flip, stack, and `sr-only`.
  - About 500 `.fa-NAME:before` codepoints run from `\f000` to `\f259`. Many are aliases that share one codepoint (group/users, euro/eur, yen/jpy/cny/rmb, save/floppy-o). The `-o` suffix was removed in FA 6.
- **Glyphicons** (Bootstrap).
  - Codes run `\e001`–`\e260`, plus Unicode escapes: `\00a5` yen, `\20bd` ruble, `\26fa` tent, `\f8ff` apple, `\231b` hourglass.
  - Aliases share one code (bitcoin/btc/xbt → `\e227`).
- **Text fonts** (Google Fonts, OFL 1.1).
  - Indie Flower (v8) and Source Sans Pro (v10, six variants) use the fallback chain eot → local → eot `?#iefix` → woff2 → woff → ttf → svg.
  - BCSans (BC government) has Bold, Regular and Italic as woff2/woff on a minio host. Bold is declared `font-weight: normal`, so it may not render bold.
- **SIL OFL 1.1:** free to use, modify and embed. Standalone font sales are not allowed. The license must be included, no reserved names may be used in derivatives, and derivatives must stay under OFL.

## 2. DataTables ecosystem
**Libraries and versions:** DataTables 1.x with the Bootstrap 3 integration, plus the Buttons extension 1.3.1 (the export code references 1.2.4 and a CDN SWF). The code is UMD-wrapped (AMD, CommonJS and browser global).

- **Bootstrap 3 integration**
  - CSS sorting icons come from Glyphicons (`\e150`, `\e155`, `\e156`).
  - JS sets `renderer='bootstrap'`, form classes and pagination markup.
  - Button classes are `btn btn-default`, inside `btn-group`, with a dropdown collection.
- **Buttons core (`Buttons` class)**
  - Per-instance `dtbN` namespaces, with a keyboard `keyup` listener and recursive `_resolveExtends` (max 30 iterations, throws on circular extends).
  - Public methods: action, active, add, container, disable, destroy, enable, name, node, processing, remove, text.
  - Static helpers: `background`, `instanceSelector`, `buttonSelector`.
  - Defaults: copy, excel, csv, pdf, print.
  - Built-in types: collection (dropdown), `pageLength`, column visibility (`colvis`, `columnsToggle`, `columnVisibility`, `colvisRestore`, `colvisGroup`), and print.
  - DataTables API: feature `"B"`, `buttons()`/`button()` selectors, `buttons.info`, `buttons.exportData` (with a shared `_exportTextarea`).
- **Export backends**
  - HTML5 path:
    - `csvHtml5` uses a Blob, FileSaver.js 1.3.3 and an optional BOM.
    - `copyHtml5` uses `execCommand('copy')` with a fallback dialog.
    - `excelHtml5` builds XLSX through JSZip. It supports JSZip 2.5 `.generate()` and 3+ `.generateAsync()`.
    - `pdfHtml5` uses pdfMake, with `vfs_fonts` required. Even rows get `#f3f3f3`.
  - Flash path: ZeroClipboard 1.0.4 with `flashExport.swf` (legacy, obsolete, chunked at 8192 characters).
  - Shared helpers: `_filename`, `_sheetname`, `_title`, `_newLine`, `_exportData`, `_setText`, `createCellPos`, `_createNode`.
  - `_excelColWidth`: length × 1.3, minimum 6, and 52 if over 40.
  - `_xlsxToStrings` and `_addToZip` use the IE token hack `_dt_b_namespace_token_` for the dropped `xmlns:r`.
- **OOXML package**
  - Files: `_rels/.rels`, `workbook.xml(.rels)`, `[Content_Types].xml`, `sheet1.xml` and `styles.xml`.
  - The sheet name is deliberately empty.
  - `styles.xml` has custom numFmts 164–169, 5 Calibri font variants, 6 fills (index 1 is the dotted-pattern quirk), 2 borders, and `cellXfs` entries (61 or 67, per different notes).
  - `_excelSpecials` regexes map cell text to style ids 56–66 for percent, currency, negative-in-parentheses, thousands and plain numbers.
  - The `tableStyles` fragment sets `TableStyleMedium9` and `PivotStyleMedium4`.

## 3. Bootstrap 3.3.7 and AdminLTE CSS bundle
- **Bootstrap 3.3.7 core:** normalize, Glyphicons, the 12-column grid (750/970/1170px containers), forms, buttons, nav/navbar, modal (z-index 1050/1040), tooltip (1070), popover (1060), carousel and print utilities.
- **Bootstrap theme:** adds gradients, shadows and IE `progid` filters.
- **AdminLTE components:** boxes, small-box, info-box, timeline, `flipInX` dropdowns and utilities.
- **Plugin styles:** social buttons (`btn-social`, lg/sm/xs sizes), Select2, FullCalendar, and the DataTables Buttons spinner, info modal and collections (z-index 2001/2002).
- **Schema-diagram CSS:** PK yellow `#dcdf8d`, FK `#BDBDBD`, unique key `#35A9FE`.

## 4. SchemaSpy 6.0.0 generated documentation
- **Shared scaffold.**
  - Head: UTF-8, IE edge, responsive viewport (`user-scalable=no`, `maximum-scale=1`), favicon `../favicon.png`, and IE8 shims (html5shiv, Respond.js).
  - Styles: Bootstrap 3.3.5, Font Awesome, Ionicons, DataTables, CodeMirror, AdminLTE all-skins, Salvattore, `schemaSpy.css`, Indie Flower and Source Sans Pro.
  - Body class: `hold-transition skin-blue layout-top-nav`.
  - Paths are `../bower/...`, so pages must sit at the expected directory depth.
- **Navbar and footer.**
  - Navbar: the brand "postgres Database", then Tables, Columns, Constraints, Relationships, Orphan Tables, Anomalies and Routines.
  - Footer: a `pull-right` block hidden on mobile, with GitHub (`fa-github-square`) and StackOverflow (`fa-stack-overflow`) icons at 2x and the text "Generated by SchemaSpy 6.0.0" (`fa-database`).
- **Script block.**
  - About 18–20 includes: jQuery 2.2.3, jQuery UI, Bootstrap, DataTables (buttons with print, colVis and HTML5), SheetJS, pdfmake with `vfs_fonts`, SlimScroll, FastClick, Salvattore, AnchorJS, CodeMirror with SQL mode, the AdminLTE app, a local `table.js` (also noted as `column.js`, `constraint.js` or `main.js`), and `schemaSpy.js` last.
  - Windows-style `.\schemaspy/images/` paths appear in one note.
- **Page-specific JS.**
  - Type-filter buttons (All / Tables / Views, Functions / Procedures) push onto `$.fn.dataTable.ext.search` with a `columnsToggle`. They use `pageLength: 50` and hardcoded column indexes (`data[1]`, `[5]`).
  - `#standard_table` and `indexes_table` have no sort or pagination.
  - Other behaviors: `anchors.add('h3')`, a read-only SQL CodeMirror, navbar active-link highlighting, and `dataTableExportButtons` (copy/Excel/CSV/PDF).
  - Image dragging uses `eval()`.
  - `$.fn.digits` is broken.
- **Page types.**
  - Per-table heads, titled "<name> - postgres Database". They include `entity`, `membership`, `org`, `org_status`, `org_type`, `user`, `contact_link`, `fee_code`, `fee_item`, `payment`, `payment_account`, `payment_line_item`, `payment_transaction`, `receipt`, `corp_type` and `filing_type`.
  - The "auth" database pages include `action_log`, `affiliation_business`, `status_code`, `user_type` and `users`.
  - The index page has a "Utility Tables" section with `alembic_version`. Its single column is `version_num` varchar(32), PK `alembic_version_pkc`.
  - The Routines page has the columns Name, Type, Language, Deterministic, Return Type and Comments.
  - Many Columns, Constraints and entity pages are empty stubs: `div.content-wrapper` > `section.content-header` > `<h1>`. Some use invalid `</br>`, and `fee_item` is truncated.
- **Sample payments and billing schema.**
  - Lookup tables use a `varchar(10)` code PK:
    - `payment_method` and `payment_system`: a description varchar(200).
    - `fee_code`: an amount float8.
    - `filing_type` (listed in the table inventory): also on the code PK pattern.
  - `payment_transaction`:
    - `id` uuid PK
    - `status_code` FK
    - `payment_id` FK
    - `pay_system_url` varchar(500)
    - `transaction_start_time` and `transaction_end_time` (timestamp)
    - `client_system_url` varchar(500)
  - `receipt`:
    - `id` serial PK
    - `invoice_id` FK
    - `receipt_number` varchar(50)
    - `receipt_date` timestamp
    - `receipt_amount` float8
  - Other tables: `payment_account`, `payment`, `payment_line_item`, `fee_schedule`, `invoice`, `alembic_version`.
  - Diagrams are static images with hardcoded `<area>` maps (PNG or SVG), at one-degree and two-degree separation.

## Caution
- **Generated and brittle files:**
  - Icon CSS and SchemaSpy pages are auto-generated, so regenerate them rather than hand-editing.
  - Hex codes, class names and font files must match exactly, and a typo fails silently.
  - Hardcoded column indexes, `cellXfs` ids 56–66 and diagram pixel maps break when the underlying structure changes.
  - Alias names share one codepoint, so editing one changes all of them.
- **Legacy and obsolete:**
  - Bower is deprecated, and bower-relative paths are fragile.
  - jQuery 2.2.3, Bootstrap 3.3.5/3.3.7, AdminLTE 2.x and Salvattore are end-of-life.
  - IE8/9 shims, `-o-`/`-ms-` prefixes, `progid` filters, `execCommand('copy')` and Flash/ZeroClipboard are dead weight.
  - Icon `-o` outline names are removed in FA 6.
  - `user-scalable=no` hurts accessibility.
- **IE hacks:** the `?#iefix` eot fragment is required for IE6–8. The `_dt_b_namespace_token_` replacement must match its pattern exactly.
- **Font and file dependencies:**
  - Glyphicons sort icons break if the font is missing.
  - pdfmake needs `vfs_fonts.js`.
  - Icon fonts render only if the font files load.
  - The BCSans Bold weight is declared as normal.
  - In CommonJS wrappers, `jszip` and `pdfmake` appear in the signature but not in the AMD requires.
  - The `datatables.net-bs` loader risks a circular require.
- **Schema and data quirks:**
  - All FKs use restrict delete.
  - PK defaults display as "null".
  - float8 is displayed as "17,17" and timestamp as "29,6", and neither is a real scale.
  - Row counts such as "1 rows" are unreliable.
  - An empty `<script src="">` on the index page will 404.
- **Conflicting numbers across notes:** check the source for these figures.
  - `cellXfs` is 61 or 67.
  - Special regex patterns are 9 or 11.
  - `_excelColWidth` has a 40 threshold or an "up to 52" cap.
  - `_setText` chunks at 8192 although the comment cites about 50KB.
- **Template inconsistencies:**
  - The `layout-top-nav` comment is confusing because the class is already applied.
  - Some heads are truncated and lack `</head>` or a body.
  - Near-identical table pages (`user_type` and `users`) should share a template.
- **Many entries are truncated:** the Bootstrap CSS, `styles.xml`, the Buttons core and the pdfMake VFS note are cut off.
