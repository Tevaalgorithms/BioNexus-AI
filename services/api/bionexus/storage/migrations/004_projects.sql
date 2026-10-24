-- Self-service project spaces. A project is a private workspace, unique per tenant.
CREATE TABLE projects (
    tenant_id    text NOT NULL,
    project_id   text NOT NULL,
    name         text NOT NULL,
    description  text NOT NULL DEFAULT '',
    created_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, project_id)
);
CREATE TABLE project_members (
    tenant_id   text NOT NULL,
    project_id  text NOT NULL,
    user_id     text NOT NULL,
    PRIMARY KEY (tenant_id, project_id, user_id),
    FOREIGN KEY (tenant_id, project_id) REFERENCES projects (tenant_id, project_id)
);
