-- Sections the condense model refused, twice, for one request (E015).
--
-- A refusal is never cached as a condensation (#221), so the section stayed
-- pending and every later sync, even over an unchanged corpus, paid two calls
-- to be refused again. One row per (section body, model name) records the
-- last refusal; `request` hashes the model fingerprint and the prompt
-- template it was asked with, so a changed body (another content_hash), a
-- repointed model or an edited prompt is a new request and is tried again.
-- `reason` and `text` are the gate's verdict and the reply it rejected, kept
-- so the operator's list can show a section that was never stored at all.
CREATE TABLE condense_refusals (
    content_hash TEXT NOT NULL REFERENCES contents(content_hash),
    model_name   TEXT NOT NULL,
    request      TEXT NOT NULL,
    reason       TEXT NOT NULL,
    text         TEXT NOT NULL,
    refused_at   TEXT NOT NULL,
    PRIMARY KEY (content_hash, model_name)
);
