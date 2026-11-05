# T3 checklist (from the merged change 4cb937f79..73c1963cb, commits cc85fec49 and 73c1963cb, issue #592)

1. A notes table keyed by stock item, many notes per item (reference:
   `stockitemnotes`), created by a database upgrade script in webERP's way
   (`sql/updates/NN.php`, next free number) and in the fresh-install schema
   (`install/sql/tables/`).
2. A maintenance script for an item's notes (reference:
   `AddStockItemNotes.php`) that follows the existing notes scripts
   (`AddCustomerNotes.php`, `AddCustomerTypeNotes.php`): add, list, edit,
   delete, with webERP's page header/footer, `$Title`, `__()` strings,
   form token (`FormID`), input escaping/validation and confirm on delete.
3. The script is registered with page security the way webERP does it (a
   security token for the new script, e.g. in the scripts table / upgrade
   script), so non-admin users with stock rights can open it.
4. Reachable from the item's page (`SelectProduct.php` menu link, with the
   selected StockID).
5. Import: the stock import (`Z_ImportStocks.php`) accepts notes and inserts
   them.
6. Nothing else regresses (the item page and import keep working).
