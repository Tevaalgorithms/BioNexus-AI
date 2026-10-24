-- Runtime-editable model catalogue (admins add / deprecate / disable models without a deploy).
CREATE TABLE model_specs (
    model_id    text PRIMARY KEY,
    payload     jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
