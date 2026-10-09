# test_a_type_with_no_syncer_fails_by_name reaches the real Notion API

What: `tests/ingest/test_syncer_dispatch.py::test_a_type_with_no_syncer_fails_by_name`
registers a `notion` source and expects the error to name "notion". Notion now
has a syncer, so the test no longer tests a missing syncer: it makes a real
request to api.notion.com. With the network up it passes on the provider's
refusal; with api.notion.com unreachable (seen from E013's sandbox) the error is
`cannot reach the provider: ConnectError`, which does not say "notion", and it
fails.

Why it matters: a test that depends on a third party's availability fails
the gate for no reason in the code, and it no longer covers what its name says.
Pick a source type that really has no syncer, or register a fake type.
