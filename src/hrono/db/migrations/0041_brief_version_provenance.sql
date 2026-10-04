-- E036: an undone hand rewrite puts back the brief it replaced, and that brief
-- was written by a model from a prompt at a cost. `brief_versions` kept only
-- the text and the model, so the restored brief had to claim 'hand-edited'.
-- The prompt and the tokens are kept too; rows kept before this migration
-- read as unknown ('' and 0).
ALTER TABLE brief_versions ADD COLUMN prompt_name TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN prompt_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE brief_versions ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE brief_versions ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0;
