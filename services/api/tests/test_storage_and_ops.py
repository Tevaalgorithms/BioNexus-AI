import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from bionexus.cli.admin import build_parser, run
from bionexus.contracts.identity import Role
from bionexus.observability import JsonFormatter, log_event, redact
from tests.conftest import fresh_postgres_storage


def test_audit_log_is_append_only_in_the_database():
    storage, db = fresh_postgres_storage()
    storage.audit.record("a", "x", "y")
    with pytest.raises(Exception, match="append-only"):
        db.execute("UPDATE audit_events SET actor = 'evil'")
    with pytest.raises(Exception, match="append-only"):
        db.execute("DELETE FROM audit_events")
    db.close()


def test_concurrent_workers_never_lease_the_same_job():
    storage, db = fresh_postgres_storage()
    from datetime import date

    from bionexus.contracts.investigation import InvestigationRequest
    from bionexus.workflow.budget import Budget
    from bionexus.workflow.state import RunState

    request = InvestigationRequest(
        disease="Crohn's disease",
        targets=("NOD2",),
        question="valid question",
        evidence_cutoff=date(2026, 1, 1),
    )
    for i in range(6):
        state = RunState(
            run_id=f"r{i}",
            tenant_id="t",
            project_id="p",
            created_by="u",
            request=request,
            release_id="rel-1",
            budget=Budget(max_cost_usd=1, max_calls=1),
        )
        storage.runs.save(state)
        storage.jobs.enqueue(f"r{i}", f"k{i}")
    now = datetime.now(UTC)
    with ThreadPoolExecutor(6) as pool:
        leased = [j for j in pool.map(lambda _: storage.jobs.lease(now), range(6)) if j]
    assert sorted(j.run_id for j in leased) == [f"r{i}" for i in range(6)]
    assert storage.jobs.lease(now) is None
    db.close()


def test_cancel_flag_survives_state_saves():
    storage, db = fresh_postgres_storage()
    from datetime import date

    from bionexus.contracts.investigation import InvestigationRequest
    from bionexus.workflow.budget import Budget
    from bionexus.workflow.state import RunState

    request = InvestigationRequest(
        disease="Crohn's disease",
        targets=("NOD2",),
        question="valid question",
        evidence_cutoff=date(2026, 1, 1),
    )
    state = RunState(
        run_id="r",
        tenant_id="t",
        project_id="p",
        created_by="u",
        request=request,
        release_id="rel-1",
        budget=Budget(max_cost_usd=1, max_calls=1),
    )
    storage.runs.save(state)
    storage.runs.request_cancel("r")
    storage.runs.save(state)  # a worker checkpoint must not clear the flag
    assert storage.runs.cancel_requested("r")
    db.close()


def test_logs_keep_only_safe_fields():
    assert redact({"run_id": "r1", "authorization": "Bearer x", "passage": "secret text"}) == {
        "run_id": "r1"
    }
    record = logging.LogRecord("bionexus", logging.INFO, "", 0, "run.finished", (), None)
    record.fields = {"run_id": "r1", "api_key": "sk-123", "status": "completed"}
    entry = json.loads(JsonFormatter().format(record))
    assert entry["run_id"] == "r1" and "api_key" not in entry and "sk-123" not in json.dumps(entry)
    log_event("no-handler-is-fine", run_id="r1")


def test_admin_cli_registers_and_revokes_users():
    storage, db = fresh_postgres_storage()
    parser = build_parser()
    args = parser.parse_args(
        [
            "add-user",
            "--subject",
            "sub-1",
            "--user-id",
            "u1",
            "--role",
            "scientist",
            "--tenant",
            "org",
            "--project",
            "p1",
            "--project",
            "p2",
        ]
    )
    run(args, storage.users)
    principal = storage.users.find_by_subject("sub-1")
    assert principal.role is Role.SCIENTIST and principal.project_ids == {"p1", "p2"}
    run(parser.parse_args(["revoke-sessions", "--subject", "sub-1"]), storage.users)
    assert storage.users.revoked_before("sub-1") is not None
    run(parser.parse_args(["disable-user", "--subject", "sub-1"]), storage.users)
    assert storage.users.find_by_subject("sub-1") is None
    db.close()
