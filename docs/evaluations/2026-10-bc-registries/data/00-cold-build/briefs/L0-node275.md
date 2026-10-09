<!-- leaf 275, 34 members -->

These condensations together describe the internals of CodeMirror 5, a browser-based text editor, in its transpiled ES5 build. The notes cover the document model, marked text, history, the display pipeline, input handling and bidirectional text. Many entries overlap. The position/span utilities, the Doc constructor and interface, the history code and the TextMarker code each appear twice in near-identical form.

## Document model and positions
- **Positions:** `cmp`, `Pos(line, ch, sticky)`, `copyPos`, `equalCursorPos`, `maxPos`/`minPos`, and the clipping family. The clipping family is `clipLine`, `clipPos`, `clipToLen` and `clipPosArray`.
- **Line storage:** The B-tree (`LeafChunk`, `BranchChunk`) holds at most 10 children per branch. `maybeSpill()` rebalances it, and a branch collapses to a single leaf below 25 lines. Lookup helpers are `getLine`, `getBetween`, `getLines`, `lineNo`, `lineAtHeight` and `isLine`.
- **Doc:**
  - The constructor takes text, mode, `firstLine`, `lineSep` and direction.
  - Content and cursor methods: `getValue`/`setValue`, `replaceRange`, `getCursor`, `setSelection`.
  - Marker and link methods: `markText`, `setBookmark`, `findMarks`, `copy`, `linkedDoc`, `unlinkDoc`.
  - Index conversion: `posFromIndex`, `indexFromPos`.
  - `updateDoc`, `linkedDocs` and `attachDoc` bind a document to an editor.
- **Line widgets and line changes:** `addLineWidget` and `LineWidget` (`clear`, `changed`) add block elements above or below a line. `changeLine` applies an operation to one line and signals `regLineChange`.

## Changes, history and selection
- **Applying edits:**
  - `makeChange` runs the `beforeChange` handlers and splits the edit on read-only ranges.
  - `makeChangeInner` adds the edit to history and propagates it to linked docs.
  - `makeChangeSingleDoc` (with `makeChangeSingleDocInEditor`) applies the change to one document and updates the editor.
  - `makeChangeFromHistory` runs undo and redo.
  - `shiftDoc` and `replaceRange` complete the set.
- **History:** The `History` object holds `done` and `undone` stacks. `addChangeToHistory` and `addSelectionToHistory` merge events by origin prefix (`+` or `*`), operation id and time window. `rebaseHist*` adjusts events after changes in linked docs. The span helpers are `attachLocalSpans`, `removeClearedSpans`, `getOldSpans`, `mergeOldSpans` and `copyHistoryArray`.
- **Selection:** `extendRange`, `extendSelection(s)`, `replaceOneSelection`, `setSelection` and `setSelectionNoUndo`. `filterSelectionChange` fires `beforeSelectionChange`. `skipAtomic` and `skipAtomicInner` keep the cursor off atomic ranges.

## Marked text
- **Span plumbing:** `MarkedSpan` and the `markedSpansBefore`/`markedSpansAfter` pair. `stretchSpansOverChange` and `clearEmptySpans` adjust spans after an edit. `removeReadOnlyRanges` splits an edit around read-only ranges. The `extraLeft`/`extraRight` pair and `compareCollapsedMarkers` handle sorting. `collapsedSpanAtSide`, `collapsedSpanAtStart` and `collapsedSpanAtEnd` find collapsed spans at line edges.
- **TextMarker:** `clear`, `find`, `changed`, `attachLine`, `detachLine` and the `markText` factory. `SharedTextMarker`, `markTextShared` and `detachSharedMarkers` handle markers shared across linked docs.
- **Folding and visual lines:** `visualLine`, `visualLineEnd`, `visualLineNo`, `lineIsHidden`, `heightAtLine`, `lineLength`, `findMaxLine` and `conflictingCollapsedRange`.

## Display pipeline
- **Display object:** The `Display` constructor builds the DOM containers.
- **View maintenance:** `regChange`, `regLineChange`, `resetView`, `viewCuttingPoint`, `adjustView` and `countDirtyView` keep the line view in sync. `DisplayUpdate` batches signals.
- **Rendering:** `updateDisplayIfNeeded`, `postUpdateDisplay`, `updateDisplaySimple` and `patchDisplay` render and sync the DOM. The gutter helpers are `updateGutters` and `setGuttersForLineNumbers`. The wheel helpers are `wheelEventDelta` and `wheelEventPixels`.
- **Smaller pieces:**
  - `startWorker`/`highlightWorker` run incremental highlighting.
  - `maybeClipScrollbars` clips native scrollbars.
  - `selectionSnapshot`/`restoreSelection` save and restore the DOM selection.

## Bidirectional text and cursor movement
- **Bidi:** `charType`, `bidiOrdering` (rules W1–W7 and N1–N2, returning `BidiSpan`s), `getOrder`, `iterateBidiSections` and `getBidiPartAt`.
- **Movement:** `moveVisually`, `moveLogically`, `moveCharLogically`, `endOfLine`, `findPosH` and `findPosV`. Unicode helpers are `isExtendingChar`, `skipExtendingChars` and `findFirst`.

## Editor operations, commands and keys
- **Editor operations:** `deleteH`, `moveV`, `findWordAt`, `toggleOverwrite`, the scroll and size methods, `swapDoc` and the DOM getters.
- **Commands and keymaps:**
  - The `commands` object holds about 30 operations. `keyMap` holds the `basic`, `pcDefault`, `emacsy` and `macDefault` bindings. `keyNames` maps key codes to names.
  - `normalizeKeyName` parses key names. `doHandleBinding`, `lookupKeyForEditor` and `dispatchKey` resolve and run bindings.
  - The electric-input helpers are `triggerElectric`, `copyableRanges`, `disableBrowserMagic` and `hiddenTextarea`.

## Input, drag-drop and infrastructure
- **Input handling:** `TextareaInput` and `ContentEditableInput` are the two input backends. `locateNodeInLineView` maps DOM nodes to line positions. The drag-drop code is `onDrop`, `onDragStart`, `onDragOver` and `clearDragCursor`. The global handlers are `registerGlobalHandlers`, `forEachCodeMirror` and `onResize`.
- **Events, features and modes:**
  - The event system: `on`, `off`, `signal`, `signalDOMEvent`, `hasHandler`, `eventMixin` and the `e_*` helpers.
  - The feature tests are `dragAndDrop`, `zeroWidthElement`, `hasBadBidiRects` and `hasBadZoomedRects`.
  - Mode registration is `defineMode` and `defineMIME`.

Caution:
- **Span partitioning:** `markedSpansBefore` and `markedSpansAfter` depend on correctly set `inclusiveLeft`, `inclusiveRight` and bookmark `insertLeft`. `stretchSpansOverChange` treats `cmp(change.from, change.to) == 0` as an insert.
- **Bidi movement and state:**
  - `moveVisually` has complex sticky-position logic, side effects that aren't isolated, and many IE6–8 workarounds.
  - `getBidiPartAt` mutates the module-level `bidiOrdering` state (`bidiOther`).
  - The `visually` flag inverts direction in RTL text.
  - `charType` indexes into encoded tables, so an off-by-one silently misclassifies characters. `lst()` is used but not defined in the snippet.
- **History:**
  - History merging depends on origin prefix, operation id and `lastModTime > time - historyEventDelay`.
  - Rebasing history over an overlapping change discards that event and all older ones.
  - `makeChangeInner` propagates to linked docs without rollback.
- **Atomic ranges:**
  - `skipAtomic` sets `doc.cantEdit = true` when the cursor is trapped, but callers don't check it.
  - Collapsed markers automatically become atomic, which affects selection.
- **Doc and tree:**
  - Most Doc methods expect positions passed through `clipPos` first. Selection ranges mix `from`/`to` and `Pos` formats.
  - `markText` overlap logic is easy to get off by one.
  - `unlinkDoc` relies on `copyHistoryArray`, which isn't shown.
  - `LeafChunk` and `BranchChunk` height bookkeeping must stay in sync. `maybeSpill()` creates a new root, so check that parent links are updated.
  - The Doc constructor works without `new` through its `instanceof` check.
- **Folding and view:**
  - `lineIsHiddenInner` recurses, so deeply nested collapsed spans risk stack overflow.
  - `lineLength` accumulates deltas across merged spans and is likely off by one.
  - `visualLineNo` differs from the real line number whenever collapsed spans exist, and many functions depend on that.
  - `lendiff` cascades through both the `viewFrom` and `viewTo` adjustments in `regChange`.
- **Display:**
  - The viewport margin optimization (keeping from/to when the distance is under 20px) can leave gaps if the margin is small.
  - Wheel pixel calibration is browser-sniffed and may flicker on the first scroll.
  - `Display` mutates the DOM and needs a valid `place` node or callback. It hardcodes IE7 z-index, and `draggable` is set only if `!webkit && !(gecko && mobile)`.
- **Drag-drop:**
  - `lastDrop` is set only on IE, so other browsers' duplicate drag events go unthrottled.
  - The file-read completion check (`++read == n`) is safe only because JavaScript is single-threaded.
- **Keys and commands:**
  - `keyNames[3]` and `keyNames[13]` both map to "Enter".
  - `keyMap["default"]` depends on the global `mac` being set at initialization.
  - `normalizeKeyName` throws on unrecognized modifiers, so a typo in a keymap becomes a runtime error.
  - `doHandleBinding` sets `suppressEdits = true` in a try block and resets it in `finally`. If `bound(cm)` throws, edits may be allowed again.
- **Platform workarounds:**
  - The hidden textarea positioning (webkit width 1000px, iOS border 1px) is fragile.
  - Electric reindent skips multi-range selections on the same line, and `electricInput` depends on correct mode setup.
  - IE-specific workarounds and the iOS `width="0px"` hack are scattered through the input code.
  - The iOS clipboard fallback silently discards inserted content.
  - Composition events trigger `poll()` without interrupting an ongoing poll, which risks a race.
  - `range()` catches exceptions from stale DOM models.
  - `locateNodeInLineView` carries a FIXME calling it "really shaky" and "likely to cause problems".
- **Editor operations:**
  - `goalColumn` tracking in `moveV` and `findPosV` is subtle.
  - `methodOp` batches operations.
  - `swapDoc` signals `swapDoc` only after detaching the old doc (`old.cm = null`).
- **Transpilation:** The ES5 build uses `var this$1 = this`, which shadows `this`.

## Members

- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-auth: docs/database-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
- sbc-pay: docs/databse-schema/bower/codemirror/codemirror.js
