<!-- leaf 166, 12 members -->

This group is a set of repeated condensations of one thing: the `<script>` include block in a SchemaSpy-generated HTML documentation page. SchemaSpy appears to be a database schema documentation tool. Each entry describes the same legacy, bower-based front-end stack, and most are near-duplicates.

## The shared stack
- **Core:** jQuery 2.2.3, jQuery UI, Bootstrap 3.3.5
- **Tables and export:** DataTables (core, Bootstrap 3 theme, and the buttons suite with HTML5, print and colVis), SheetJS (xlsx), pdfmake
- **UI helpers:** SlimScroll, FastClick, Salvattore, AnchorJS
- **Editor:** CodeMirror with SQL mode
- **Theme:** the AdminLTE app script
- **Local scripts:** `schemaSpy.js`, always loaded last

## Variations
- **Local script name:** the custom script before `schemaSpy.js` is called `column.js` in one entry, `constraint.js` in two, `main.js` in one, and `table.js` in the rest. This is the only real difference in content.
- **Fragment views:** two entries cover only part of the list. One covers the tail, from slimScroll through `table.js` and `schemaSpy.js`. Another describes an 18-tag fragment with paths of the form `../bower/...`.
- **Wording:** the "Loads 20+ scripts from bower_components and local" entry is repeated verbatim six times. The "Script includes (all from `bower/`)" entry appears twice.

## Observations
- Scripts load in a fixed order: libraries first, then the AdminLTE app script, then the local scripts.
- Paths are relative, with a `../bower/` prefix.
- One entry notes hardcoded `.\schemaspy/images/` paths, which suggests the files were generated on Windows.

Caution:
- Bower has been deprecated since about 2017. One entry suggests migrating to npm.
- jQuery 2.2.3 (about 2016) and Bootstrap 3.3.5 (about 2015) are end-of-life. Modernization is recommended.
- pdfmake needs `vfs_fonts.js` loaded separately, or embedded fonts won't render.
- The page depends heavily on the AdminLTE ecosystem, and no module bundling is visible.
- The relative `../bower/...` paths only work if the HTML sits at the expected directory depth. One entry says exactly 2 levels deep.
- There are no integrity hashes or version pins, so there's no way to tell whether the bower components are out of date.
- The hardcoded Windows-style backslash path `.\schemaspy/images/` suggests Windows-specific generation and may break elsewhere.

## Members

- sbc-auth: docs/database-schema/columns.html
- sbc-auth: docs/database-schema/constraints.html
- sbc-auth: docs/database-schema/index.html
- sbc-auth: docs/database-schema/tables/contact.html
- sbc-auth: docs/database-schema/tables/contact_link.html
- sbc-auth: docs/database-schema/tables/entity.html
- sbc-auth: docs/database-schema/tables/membership.html
- sbc-auth: docs/database-schema/tables/membership_type.html
- sbc-auth: docs/database-schema/tables/org.html
- sbc-auth: docs/database-schema/tables/org_type.html
- sbc-auth: docs/database-schema/tables/user.html
- sbc-pay: docs/databse-schema/constraints.html
