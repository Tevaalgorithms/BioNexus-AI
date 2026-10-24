from fastapi.testclient import TestClient

from bionexus.api.app import create_app
from bionexus.sources.registry import SOURCE_META, SOURCE_NAMES


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_every_source_describes_how_it_is_reached(container):
    client = TestClient(create_app(container))
    rows = {r["name"]: r for r in client.get("/admin/sources", headers=auth("admin")).json()}
    assert set(rows) == set(SOURCE_NAMES) == set(SOURCE_META)
    for row in rows.values():
        assert (
            row["label"]
            and row["host"]
            and row["provides"]
            and row["protocol"] in {"REST", "GraphQL"}
        )


def test_source_check_reports_latency(container):
    client = TestClient(create_app(container))
    result = client.post("/admin/sources/gwas/check", headers=auth("admin")).json()
    assert result["ok"] and isinstance(result["latency_ms"], int)


def test_skills_endpoint_explains_each_active_skill(container):
    client = TestClient(create_app(container))
    payload = client.get("/admin/skills", headers=auth("admin")).json()
    assert {s["skill_id"] for s in payload["skills"]} == set(payload["versions"])
    first = payload["skills"][0]
    assert first["approved"] and first["instructions"] and len(first["content_hash"]) == 64
