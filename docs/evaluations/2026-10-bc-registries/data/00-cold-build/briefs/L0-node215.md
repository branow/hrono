<!-- leaf 215, 32 members -->

This is a set of condensed notes on a bundled, browserified copy of **cheerio** (a jQuery-like server-side DOM library) and its dependency stack: css-select/css-what, domutils/domhandler, dom-serializer, htmlparser2, and parse5. There are also a few wrapper and glue fragments. Most entries are per-module summaries, each with its own gotchas.

## Groupings

**1. Bundle and wrapper glue**
- UMD wrapper that sets `g.cheerio = f()`.
- Cheerio package exports: re-exports `load`, `html`, `text` and `xml`, and marks `contains`, `merge`, `parseHTML` and `root` as deprecated.
- Postman registration: `postman[Extend].module.cheerio` via `Symbol.for('extend')`.
- Dependency occurrence counts: `./helpers` (4), `./positionals` (6), `css-select` (24), `css-what` (32), `domutils` (43).

**2. Cheerio core**
- Modules 12–15:
  - The `Cheerio` constructor.
  - `load()`.
  - Default options `{xml: false, decodeEntities: true}`, plus `flatten()`.
  - `parse()`, which chooses htmlparser2 or parse5.

**3. Cheerio API mixins** (methods added to the prototype)
- **Attributes, classes and forms:**
  - `getAttr`/`setAttr`, `getProp`/`setProp` and `readData`.
  - `val`, `removeAttr`, `hasClass`, `addClass`, `removeClass`, `toggleClass` and `is`.
- **CSS:** `css`, with `setCss`, `getCss`, `parse` and `stringify`.
- **Manipulation:**
  - Insertion: `append`, `prepend`, `after`, `before`, `appendTo`, `prependTo`, `insertAfter`, `insertBefore`, built on `uniqueSplice`.
  - Wrapping: `wrap`, `wrapInner`, `wrapAll`, `unwrap`.
  - Removal and replacement: `remove`, `replaceWith`, `empty`.
  - Content and cloning: `html`, `text`, `toString`, `clone`.
- **Traversal:**
  - Tree walking: `find`, `parent`, `parents`, `parentsUntil`, `closest`, `children`, `contents`, `siblings`.
  - Sibling walking: `next`, `nextAll`, `nextUntil`, `prev`, `prevAll`, `prevUntil`.
  - Iteration and filtering: `each`, `map`, `filter`, `not`, `has`.
  - Selection and indexing: `first`, `last`, `eq`, `get`, `index`, `slice`, `end`, `add`, `addBack`.
  - The helper `traverseParents`.

**4. Positional and filter selectors** (cheerio's own layer over css-select)
- Selector grouping: `getDocumentRoot` and `groupSelectors`.
- Filter search: `findFilterElements`, `findElements`, `find` and `filterElements`.
- Filter names and limits: `filterNames`, `isFilter` and `getLimit`.

**5. css-select and css-what**
- Compiler: `compile`, `compileUnsafe`, `compileToken` and `compileGeneralSelector`.
- Pseudo-class filters: `contains`, `nth-*` and `scope`.
- Pseudos and subselects: `empty`, `first-child` and similar, plus `is`, `not` and `has`.
- Cost-based ordering: `sortByProcedure` and `getProcedure`.
- Module 34: selector `stringify`.

**6. domutils and domhandler**
- DOM node model: the `Element` class and `cloneNode`.
- Node utilities: `removeSubsets`, `compareDocumentPosition`, `uniqueSort` and re-exported predicates.
- Querying and mutation: `Checks`, `testElement`, `getElements` and similar, plus `removeElement`, `replaceElement`, `append` and `prepend`.
- Search and text:
  - Search: `filter`, `find`, `findOne`, `findAll` and `existsOne`.
  - Text and HTML output: `getText`, `textContent`, `innerText`, `getOuterHTML` and `getInnerHTML`.
- Accessors: `getChildren`, `getParent`, `getSiblings`, `getAttributeValue` and similar.
- Feeds: `getFeed`, with Atom and RSS parsing and media keys.

**7. parse5 internals**
- `FormattingElementList`, including the Noah's Ark rule.
- Parser boilerplate: 28 insertion modes, the adoption-agency loop caps (8 outer, 3 inner), and the incomplete `TOKEN_HANDLERS`.
- Tag helpers: `isImpliedEndTagRequired`, `isImpliedEndTagRequiredThoroughly` and `isScopingElement`.
- Mixin infrastructure: `mergeOptions` and `Mixin`, with `install` and `_getOverriddenMethods`.

## Caution:
- **Global overwrite:** `g.cheerio = f()` overwrites any existing `cheerio` global. If several scripts define it, the last one wins, so load order matters.
- **Postman registration:** `Symbol.for('extend')` is a global symbol. The `postman` object must already have the `[Extend]` key set.
- **Dependency counts:** The numbers don't show depth, size, stability or criticality.
- **Minified source:** The bundle is browserified and minified. Changes need the original source files.
- **Deprecated imports:** Re-exported domhandler predicates and `getOuterHTML`/`getInnerHTML` are deprecated. Import from `domhandler` or `dom-serializer` directly.
- **Filter limits:**
  - `gt` returns ∞ for any finite number, including 0, and 0 for NaN.
  - `lt` returns ∞ for a negative number.
  - So the two are asymmetric.
- **Selector scoping and recursion:**
  - Special traversals get `SCOPE_PSEUDO` prepended to stop matches leaking.
  - The order of `unshift` matters, because the regex alternation must list the longest option first.
  - Malformed selectors have no recursion depth limit.
- **Selector compilation:**
  - `FLEXIBLE_DESCENDANT_TOKEN` is undocumented, so its difference from the standard descendant token is unclear.
  - The `isFalseCache` only memoizes failures.
  - The adjacent-sibling fallback scans backwards in O(n).
  - `xmlMode` controls tag and attribute case together.
- **Pseudo filters:**
  - `nth-*` filters short-circuit to `trueFunc` or `falseFunc` and skip `next()`.
  - `:has` and `:contains` always get the most expensive cost (0).
  - `getText` is expensive.
  - `PLACEHOLDER_ELEMENT` is a mutable `{}`, not a real element.
- **Stringify:** The attribute shorthand (`#id`, `.class`) requires `ignoreCase === "quirks"` as a string.
- **Attributes:**
  - Radio and checkbox `.value` is hardcoded to `'on'`, which can mislead form serialization.
  - `val()` on a select returns an array only when `multiple` is set.
  - Setting a select value needs `removeAttr('selected')` first.
- **Classes:**
  - `hasClass` uses boundary checks to avoid substring matches.
  - `removeClass` uses `j--` after splice to handle duplicates.
- **CSS accessor:** `getCss` returns undefined if the element or its `attribs` is falsy, and `.split(';')` on undefined would crash.
- **Manipulation:**
  - `uniqueSplice` removes nodes from their old parent first, so index adjustment matters when inserting into the same parent.
  - Node lifecycle is easy to leak if a node is reinserted without `updateDOM`.
  - `unwrap` silently skips `body`.
  - `insertAfter` and `insertBefore` clone and remove the originals, so identity is lost.
  - `after` and `before` callbacks get `(i, currentHtml)`, which is poorly documented.
- **Traversal:**
  - `parents()` returns results in reverse order, deduplicated.
  - `find()` bypasses children filtering for `~` and `+`.
  - `each` stops only on an explicit `return false`.
  - `prevAll` keeps traversal order, not document order.
  - `filter` and `not` accept a container override. A Cheerio object uses its `.is()`.
  - `eq(0)` returns `this` when length ≤ 1.
  - `index()` detects Cheerio objects through the `.cheerio` property.
  - `get()` returns raw nodes.
- **Constructor and options:**
  - Option merge order matters, and `flattenOptions()` can override `xml`.
  - Context defaults to `_root`, which may be undefined.
- **domhandler and domutils:**
  - The `Element` constructor auto-assigns the Script or Style type from the tag name, ignoring the type parameter.
  - `x-attribsNamespace` and `x-attribsPrefix` are non-standard internal keys.
  - `findOne` skips non-tag nodes.
  - `findAll` is iterative pre-order, so its order differs from `find`.
  - `getSiblings` rebuilds the sibling list by walking pointers when there is no parent, which is costly for long chains.
  - The RSS feed type is the first 3 characters of the root name.
- **parse5:**
  - Noah's Ark proactively removes duplicate formatting elements beyond 3.
  - A mismatched insertion mode parses incorrectly.
  - The adoption-agency loop caps exist to prevent runaway processing.
  - `isScopingElement` depends on namespace as well as tag name.
- **Mixin and options:**
  - `Object.create(null)` has no prototype, which breaks `instanceof` and inherited methods.
  - `_getOverriddenMethods()` throws unless a subclass overrides it.
  - `host.__mixins` is mutated directly.
  - `install()` compares constructors, not instances.

## Members

- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/cheerio.js
- lear: legal-api/tests/performance/libs/shim/cheerio.js
