ALTER TABLE runs ADD COLUMN cancel_requested boolean NOT NULL DEFAULT false;

CREATE TABLE system_flags (
    name   text PRIMARY KEY,
    value  boolean NOT NULL
);
