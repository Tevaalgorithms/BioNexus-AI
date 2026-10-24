import pytest
from fastapi.testclient import TestClient

from bionexus.api.app import create_app

BODY = {
    "disease": "Crohn's disease",
    "targets": ["NOD2", "IL23R"],
    "question": "Compare NOD2 sensing and IL-23 signalling.",
    "evidence_cutoff": "2026-01-01",
}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(container):
    return TestClient(create_app(container))


def submit(client, token="sci", key="k1"):
    headers = {**auth(token), "Idempotency-Key": key}
    return client.post("/projects/proj-1/investigations", json=BODY, headers=headers)


def test_missing_or_unknown_token_is_denied(client):
    assert client.get("/admin/release").status_code == 403
    assert client.get("/admin/release", headers=auth("nope")).status_code == 403


def test_scientist_cannot_use_admin_apis(client):
    assert client.get("/admin/release", headers=auth("sci")).status_code == 403
    body = {"binding": {"model_id": "fixture-large"}, "reason": "x", "expected_revision": 1}
    assert (
        client.put("/admin/agents/literature/binding", json=body, headers=auth("sci")).status_code
        == 403
    )


def test_admin_has_no_implicit_access_to_project_data(client):
    assert submit(client, token="admin").status_code == 403


def test_other_tenant_cannot_read_a_run_or_report(client):
    run_id = submit(client).json()["run_id"]
    assert client.get(f"/investigations/{run_id}", headers=auth("outsider")).status_code == 403
    assert (
        client.get(f"/investigations/{run_id}/report", headers=auth("outsider")).status_code == 403
    )


def test_submit_review_and_approve_flow(client):
    run_id = submit(client).json()["run_id"]
    assert (
        client.get(f"/investigations/{run_id}", headers=auth("sci")).json()["status"]
        == "waiting_for_review"
    )
    report = client.get(f"/investigations/{run_id}/report", headers=auth("sci")).json()

    stale = client.post(
        f"/investigations/{run_id}/report/approve",
        json={"report_hash": "stale"},
        headers=auth("sci"),
    )
    assert stale.status_code == 409

    ok = client.post(
        f"/investigations/{run_id}/report/approve",
        json={"report_hash": report["content_hash"]},
        headers=auth("sci"),
    )
    approved = ok.json()
    assert approved["status"] == "approved" and approved["parent_version"] == 1
    assert (
        client.get(f"/investigations/{run_id}", headers=auth("sci")).json()["status"] == "completed"
    )


def test_admin_rebind_applies_to_new_runs_only(client):
    old_run = submit(client, key="old").json()["run_id"]
    body = {
        "binding": {"model_id": "fixture-large"},
        "reason": "quality trial",
        "expected_revision": 1,
    }
    assert (
        client.put("/admin/agents/literature/binding", json=body, headers=auth("admin")).status_code
        == 200
    )

    new_run = submit(client, key="new").json()["run_id"]
    status = lambda r: client.get(f"/investigations/{r}", headers=auth("sci")).json()["release_id"]  # noqa: E731
    assert (status(old_run), status(new_run)) == ("rel-1", "rel-2")

    manifest = client.get(f"/investigations/{new_run}/report", headers=auth("sci")).json()[
        "manifest"
    ]
    literature_models = {
        c["model_id"] for c in manifest["model_calls"] if c["agent"] == "literature"
    }
    assert literature_models == {"fixture-large"}


def test_stale_admin_revision_is_a_conflict_and_unknown_model_is_rejected(client):
    stale = {"binding": {"model_id": "fixture-large"}, "reason": "x", "expected_revision": 9}
    assert (
        client.put("/admin/agents/critic/binding", json=stale, headers=auth("admin")).status_code
        == 409
    )
    unknown = {"binding": {"model_id": "arbitrary-url"}, "reason": "x", "expected_revision": 1}
    assert (
        client.put("/admin/agents/critic/binding", json=unknown, headers=auth("admin")).status_code
        == 422
    )
