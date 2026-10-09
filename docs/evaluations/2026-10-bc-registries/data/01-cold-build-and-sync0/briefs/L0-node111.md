<!-- leaf 111, 9 members -->

This collection is a set of near-duplicate summaries of one HATEOAS link block. The block comes from a REST API response on `https://heineken.cas.gov.bc.ca:7019/ords/cas/cfs/`, an Oracle ORDS endpoint. Every copy uses the same hierarchy of party 11111, account 4101 and site 29921. Most copies describe the invoice-level link set. A few describe only a partial fragment.

**Invoice-level link set (full rel list)**
- Rels: collection, parent, self, deposits, credit_memos, receipts, adjustments.
- Path pattern: `.../parties/{id}/accs/{id}/sites/{id}/invs/{id}/[resource]/`.
- Variations by invoice ID:
  - Invoice 10021: the most frequent version, repeated several times. Parent and self point to it.
  - Invoice 10022: one summary covers it, and another notes a stub entry for 10022 that is incomplete.
  - Invoice 10023: one summary covers it.

**Partial fragments (receipts and adjustments only)**
- Receipts link: `.../sites/29921/rcpts/`, the same in every fragment.
- Adjustments link: `.../invs/{10021, 10022 or 10023}/adjs/`.
- The JSON is truncated mid-value (`inv_info3` is incomplete).

**Caution:**
- The adjustments href has a trailing space before the closing quote (`.../adjs/ `). Strict clients may fail to parse the URL or route on it unless it is trimmed.
- The JSON excerpt is malformed or incomplete, cut off mid-value. Parsing may fail.
- The IDs (11111, 4101, 29921, 10021–10023) appear to be literal example values. Real responses will differ, so confirm the IDs are dynamic and not hardcoded test data.

## Members

- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
