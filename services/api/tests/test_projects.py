import pytest
from fastapi.testclient import TestClient

from bionexus.api.app import create_app
from bionexus.container import build_container
from bionexus.contracts.identity import ClientKind, Principal, Role
from tests.conftest import TOKENS

COLLEAGUE = Principal(
    user_id="sci-3", role=Role.SCIENTIST, tenant_id="org-a", client_kind=ClientKind.SCIENTIST
)
OTHER_ORG = Principal(
    user_id="sci-9", role=Role.SCIENTIST, tenant_id="org-b", client_kind=ClientKind.SCIENTIST
)


@pytest.fixture
def client(storage):

    tokens = {**TOKENS, "colleague": COLLEAGUE, "other-org": OTHER_ORG}
    # the user directory is how a project owner finds colleagues to invite
    for subject, principal in tokens.items():
        storage.users.upsert(subject, principal)
    app = build_container(tokens, storage=storage)
    return TestClient(create_app(app))


def auth(token):
    return {"Authorization": f"Bearer {token}"}


BODY = {
    "disease": "Crohn's disease",
    "targets": ["NOD2"],
    "question": "valid question here",
    "evidence_cutoff": "2026-01-01",
}


def test_scientist_creates_a_project_and_can_immediately_use_it(client):
    created = client.post(
        "/projects",
        json={"name": "COVID-19 host genes", "description": "ACE2 study"},
        headers=auth("sci"),
    )
    assert created.status_code == 201 and created.json()["project_id"] == "covid-19-host-genes"
    assert "covid-19-host-genes" in [
        p["project_id"] for p in client.get("/projects", headers=auth("sci")).json()
    ]
    run = client.post(
        "/projects/covid-19-host-genes/investigations",
        json=BODY,
        headers={**auth("sci"), "Idempotency-Key": "k"},
    )
    assert run.status_code == 202


def test_projects_listing_marks_ownership_and_keeps_operator_assigned_ones(client):
    client.post("/projects", json={"name": "My study"}, headers=auth("sci"))
    rows = {p["project_id"]: p for p in client.get("/projects", headers=auth("sci")).json()}
    assert rows["my-study"]["owner"] is True and rows["proj-1"]["owner"] is False


@pytest.mark.parametrize("name", ["ab", "x" * 81, "!!!", "   "])
def test_bad_names_are_rejected(client, name):
    assert client.post("/projects", json={"name": name}, headers=auth("sci")).status_code == 422


def test_duplicate_names_conflict_within_an_organisation_but_not_across(client):
    assert (
        client.post("/projects", json={"name": "Shared name"}, headers=auth("sci")).status_code
        == 201
    )
    assert (
        client.post("/projects", json={"name": "shared  NAME"}, headers=auth("sci")).status_code
        == 409
    )
    assert (
        client.post(
            "/projects", json={"name": "Shared name"}, headers=auth("other-org")
        ).status_code
        == 201
    )


def test_admins_cannot_create_project_spaces(client):
    assert (
        client.post("/projects", json={"name": "Admin project"}, headers=auth("admin")).status_code
        == 403
    )


def test_other_organisations_cannot_see_or_use_a_project(client):
    client.post("/projects", json={"name": "Private study"}, headers=auth("sci"))
    ids = [p["project_id"] for p in client.get("/projects", headers=auth("other-org")).json()]
    assert "private-study" not in ids
    run = client.post(
        "/projects/private-study/investigations",
        json=BODY,
        headers={**auth("other-org"), "Idempotency-Key": "k"},
    )
    assert run.status_code == 403


def test_owner_invites_a_colleague_who_then_gains_access(client):
    client.post("/projects", json={"name": "Team study"}, headers=auth("sci"))
    denied = client.post(
        "/projects/team-study/investigations",
        json=BODY,
        headers={**auth("colleague"), "Idempotency-Key": "k"},
    )
    assert denied.status_code == 403
    invited = client.post(
        "/projects/team-study/members", json={"user_id": "sci-3"}, headers=auth("sci")
    )
    assert invited.status_code == 201 and set(invited.json()) == {"sci-1", "sci-3"}
    allowed = client.post(
        "/projects/team-study/investigations",
        json=BODY,
        headers={**auth("colleague"), "Idempotency-Key": "k2"},
    )
    assert allowed.status_code == 202


def test_only_the_owner_can_invite_and_only_known_colleagues_in_the_same_organisation(client):
    client.post("/projects", json={"name": "Owner only"}, headers=auth("sci"))
    client.post("/projects/owner-only/members", json={"user_id": "sci-3"}, headers=auth("sci"))
    by_member = client.post(
        "/projects/owner-only/members", json={"user_id": "sci-3"}, headers=auth("colleague")
    )
    assert by_member.status_code == 403
    assert (
        client.post(
            "/projects/owner-only/members", json={"user_id": "ghost"}, headers=auth("sci")
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/projects/owner-only/members", json={"user_id": "sci-9"}, headers=auth("sci")
        ).status_code
        == 404
    )
    assert client.get("/projects/owner-only/members", headers=auth("outsider")).status_code == 403


def test_reviewed_memory_is_scoped_to_the_new_project(client):
    client.post("/projects", json={"name": "Memory A"}, headers=auth("sci"))
    client.post("/projects", json={"name": "Memory B"}, headers=auth("sci"))
    run = client.post(
        "/projects/memory-a/investigations",
        json=BODY,
        headers={**auth("sci"), "Idempotency-Key": "a"},
    ).json()["run_id"]
    report = client.get(f"/investigations/{run}/report", headers=auth("sci")).json()
    client.post(
        f"/investigations/{run}/report/approve",
        json={"report_hash": report["content_hash"]},
        headers=auth("sci"),
    )
    second = client.post(
        "/projects/memory-b/investigations",
        json=BODY,
        headers={**auth("sci"), "Idempotency-Key": "b"},
    ).json()["run_id"]
    detail = client.get(f"/investigations/{second}/detail", headers=auth("sci")).json()
    assert all(e["review_state"] != "reviewed" for e in detail["evidence"])
