<!-- leaf 38, 13 members -->

This set is a collection of condensed notes on **browserify-style bundle internals**: the UMD/global-detection wrapper stubs and the Node-compat shims (process, events, util) that get bundled with them. The notes are heavily repetitive, and several entries are duplicated verbatim.

## 1. UMD / global-scope wrapper stubs
These are the most common entries. They are all variations of one pattern: an IIFE call `(this, require('_process'), <global detection>)`.

- **Core pattern:** the global fallback chain is `global` (Node) → `self` (Web Worker) → `window` (browser) → `{}`.
- **Variations:**
  - The basic form passes `this`, `require('_process')` and the global chain. It appears about 4 times, with identical wording.
  - The extended form adds `require("timers").setImmediate` as a fourth argument. It appears twice.
  - A prose-only description of the chain, starting from `this`, appears twice.
- **Library-specific wrappers:**
  - **aws4:** a UMD export to CommonJS, AMD, or a browser global (`g.aws4 = f()`). The function body is truncated.
  - **lodash:** the tail of a UMD bundle, with entry point "lodash". The actual module code precedes it.

## 2. Node core-module polyfills
- **events (EventEmitter):**
  - Covers `prependOnceListener`, `removeListener` and `removeAllListeners`.
  - Also covers `listeners`, `rawListeners`, `listenerCount` and `eventNames`.
  - Helpers: `spliceOne`, `arrayClone`, `unwrapListeners`, and polyfills for Object.create, Object.keys and Function.bind.
  - `removeListener` scans arrays in reverse and backfills `events[type]` when the array collapses to one listener.
- **process shim:**
  - Caches `setTimeout`/`clearTimeout`, wrapped in try/catch.
  - Provides `runTimeout`, `runClearTimeout` and a queue-based `process.nextTick`.
  - Stubs `on/off/emit/binding/cwd/chdir/umask`.
  - Gives trivial values for `title`, `browser`, `env`, `argv`, `version` and `versions`.
- **util-style modules (197, 198):**
  - Module 197 holds the type checks `isString`, `isObject`, `isNull` and `isNullOrUndefined`.
  - Module 198 is a deprecation wrapper. It warns once, or throws or traces, depending on the localStorage flags `noDeprecation`, `throwDeprecation` and `traceDeprecation`.

## Caution:
- The aws4 wrapper's function body is truncated, so no actual module code is shown.
- `require('_process')` uses a non-standard underscore-prefixed name. The wrapper looks like a UMD or browserify factory parameter list.
- The `{}` fallback silently masks a missing global, so code proceeds without error. `setImmediate` binding may also fail in restricted environments.
- `this` binding depends on call context (strict vs. non-strict, module vs. script), so it may not be what you expect.
- The lodash wrapper is only the tail of the bundle. The module code precedes it.
- `objectKeysPolyfill` returns `k` instead of `keys`. This bug returns the last key iterated, not the array.
- In the process shim, the try/catch is deliberately wrapped in a function because it deoptimizes in some engines. Do not inline it.
- Deprecation flags depend on localStorage, so sandboxed iframes silently fall back to false for all flags.

## Members

- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/chai.js
- lear: legal-api/tests/performance/libs/lodash.js
- lear: legal-api/tests/performance/libs/xml2js.js
- lear: legal-api/tests/performance/libs/xml2js.js
