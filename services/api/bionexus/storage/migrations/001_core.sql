-- Core tenant-aware schema. Every private row carries tenant_id (DATA-04).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE runs (
    run_id      text PRIMARY KEY,
    tenant_id   text NOT NULL,
    project_id  text NOT NULL,
    status      text NOT NULL,
    state       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX runs_scope_idx ON runs (tenant_id, project_id);

CREATE TABLE jobs (
    job_id           text PRIMARY KEY,
    run_id           text NOT NULL REFERENCES runs (run_id),
    idempotency_key  text NOT NULL UNIQUE,
    done             boolean NOT NULL DEFAULT false,
    attempts         integer NOT NULL DEFAULT 0,
    lease_expires    timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reports (
    report_id  text PRIMARY KEY,
    run_id     text NOT NULL REFERENCES runs (run_id),
    version    integer NOT NULL,
    payload    jsonb NOT NULL,
    UNIQUE (run_id, version)
);

CREATE TABLE audit_events (
    id      bigserial PRIMARY KEY,
    actor   text NOT NULL,
    action  text NOT NULL,
    detail  text NOT NULL,
    at      timestamptz NOT NULL DEFAULT now()
);
-- Append-only: block updates and deletes at the database level.
CREATE FUNCTION audit_is_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER audit_no_change BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_is_append_only();

CREATE TABLE memory_items (
    tenant_id    text NOT NULL,
    project_id   text NOT NULL,
    evidence_id  text NOT NULL,
    target       text NOT NULL,
    record       jsonb NOT NULL,
    PRIMARY KEY (tenant_id, project_id, evidence_id)
);

CREATE TABLE releases (
    release_id  text PRIMARY KEY,
    revision    integer NOT NULL UNIQUE,
    payload     jsonb NOT NULL,
    is_active   boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX releases_one_active ON releases (is_active) WHERE is_active;

CREATE TABLE app_users (
    subject          text PRIMARY KEY,
    user_id          text NOT NULL UNIQUE,
    role             text NOT NULL CHECK (role IN ('platform_admin', 'scientist')),
    tenant_id        text NOT NULL,
    active           boolean NOT NULL DEFAULT true,
    revoked_before   timestamptz
);
CREATE TABLE memberships (
    subject     text NOT NULL REFERENCES app_users (subject),
    project_id  text NOT NULL,
    PRIMARY KEY (subject, project_id)
);

-- seq is globally monotonic, so concurrent writers never collide; clients resume with "after seq".
CREATE TABLE run_events (
    seq     bigserial PRIMARY KEY,
    run_id  text NOT NULL,
    kind    text NOT NULL,
    data    jsonb NOT NULL
);
CREATE INDEX run_events_run_idx ON run_events (run_id, seq);
