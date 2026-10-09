<!-- leaf 124, 6 members -->

This group is a set of near-duplicate condensations of one small HTML snippet. The snippet is a footer: a closing `</div>` followed by a script that sets `config = { pagination: true }`. The entries differ only in wording and in which problems they flag.

**Groupings**

1. **Truncated script tag (3 entries).** Each says the config object has `pagination: true` and a closing div follows. Each flags that the `<script>` has no closing `</script>`, so the snippet is likely truncated or malformed.

2. **Dangling div and unclear scope (2 entries).** Each says the script sets `config.pagination = true` and the div closure is incomplete. Each flags the dangling `</div>` as a sign the HTML context was lost. Each also asks whether `config` is declared in the global scope or by a parent script.

3. **Global-scope config (1 entry, titled "HTML Footer & Script Config").** It says the snippet closes the content div and sets `config = { pagination: true }`. It flags that `config` sits in the global scope with no namespace protection, so it may collide with other scripts.

**Caution:**
- The `<script>` tag has no closing `</script>`, so the snippet may be truncated or malformed.
- The closing `</div>` is dangling, which suggests the surrounding HTML was lost.
- The scope of `config` is unclear. It is either undeclared or global, and a global `config` has no namespace protection and may collide with other scripts.

## Members

- sbc-auth: docs/database-schema/columns.html
- sbc-auth: docs/database-schema/constraints.html
- sbc-auth: docs/database-schema/index.html
- sbc-pay: docs/databse-schema/columns.html
- sbc-pay: docs/databse-schema/constraints.html
- sbc-pay: docs/databse-schema/index.html
