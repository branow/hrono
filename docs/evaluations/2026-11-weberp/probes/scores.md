# Familiarity probe scores

Run 2026-11-05T12:03:08Z, Claude Code 2.1.287, `claude -p <q> --model sonnet
--tools "" --strict-mcp-config --setting-sources "" --no-session-persistence
--output-format json`, from an empty directory, stdin /dev/null. Model as
reported: claude-sonnet-5-5. Raw answers: a1.json, a2.json, a3.json (cost
$0.022033, $0.014983, $0.015439). Scored by Claude Opus 5.5 against
ground-truth.md.

| Q | score | why |
|---|---|---|
| 1 | wrong | gave CustomerAccount.php's expression but attributed it to CustomerInquiry.php and AgedDebtors.php, which use ADDDATE(last_day(...)); did not know the two differ |
| 2 | partial | right that the daily update only rewrites currencies.rate (hedged as "don't know" for bank balances); wrong file: names includes/UpdateCurrencyRates.php, which does not exist (the code is in includes/LoginFunctions.php) |
| 3 | wrong | asserted one shared account (exchangediffact); supplier allocations post to purchasesexchangediffact |

Verdict: Sonnet knows webERP's general vocabulary (table and config names)
but not where its rules live or how the copies differ. Low familiarity, so
webERP is usable.
