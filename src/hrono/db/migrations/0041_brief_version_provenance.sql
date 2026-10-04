-- E036: an undone hand rewrite puts back the brief it replaced, and that brief
-- was written by a model from a prompt at a cost. `brief_versions` kept only
-- the text and the model, so the restored brief had to claim 'hand-edited'.
-- The whole record is kept too: prompt, tokens, members, source model,
-- fingerprint, member signature and the gates' verdicts. Rows kept before this
-- migration read as unknown ('' and 0), and an empty signature never matches,
-- so a hand-back re-briefs them.
ALTER TABLE brief_versions ADD COLUMN prompt_name TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN prompt_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE brief_versions ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE brief_versions ADD COLUMN member_signature TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN members TEXT NOT NULL DEFAULT '[]';
ALTER TABLE brief_versions ADD COLUMN source_model TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN model_fingerprint TEXT;
ALTER TABLE brief_versions ADD COLUMN unfaithful TEXT NOT NULL DEFAULT '[]';
ALTER TABLE brief_versions ADD COLUMN flagged TEXT NOT NULL DEFAULT '';
