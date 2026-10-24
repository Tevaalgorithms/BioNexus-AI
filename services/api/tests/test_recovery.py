from datetime import UTC, datetime, timedelta

import pytest

from bionexus.contracts.errors import SourceUnavailable
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.workflow.runner import thread
from tests.conftest import SCIENTIST


class Crash(Exception):
    pass


def test_graph_resumes_from_its_checkpoint_after_a_crash(container, request_):
    """A crash in `retrieve` must not redo scope, memory recall, specialists or critique."""
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    nodes = container.nodes
    real_retrieve, calls = nodes.retrieve, {"specialists": 0}
    real_specialists = nodes.specialists

    def counting_specialists(state):
        calls["specialists"] += 1
        real_specialists(state)

    def crash(state):
        raise Crash

    nodes.specialists, nodes.retrieve = counting_specialists, crash
    state = container.storage.runs.load(run.run_id)
    state.transition(InvestigationStatus.RUNNING)
    container.storage.runs.save(state)

    with pytest.raises(Crash):
        container.graph.invoke({"run_id": run.run_id, "repair_round": 0}, thread(run.run_id))
    assert container.graph.get_state(thread(run.run_id)).next == ("retrieve",)

    nodes.retrieve = real_retrieve  # "restarted worker" with the bug fixed
    container.graph.invoke(None, thread(run.run_id))
    assert calls["specialists"] == 1  # not repeated
    saved = container.storage.runs.load(run.run_id)
    assert saved.report_id == f"{run.run_id}-v1" and saved.claims


def test_expired_lease_resumes_the_same_run_without_a_second_investigation(container, request_):
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    now = datetime.now(UTC)
    container.storage.jobs.lease(now)  # a worker took the job and died
    assert container.worker.run_pending(now=now) == 0  # lease still held
    assert container.worker.run_pending(now=now + timedelta(hours=1)) == 1
    final = container.storage.runs.load(run.run_id)
    assert final.status is InvestigationStatus.WAITING_FOR_REVIEW
    assert len(container.storage.reports.versions(run.run_id)) == 1  # finalised exactly once


def test_transient_source_failures_are_retried_then_succeed(container, request_):
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    real, attempts = container.nodes.specialists, {"n": 0}

    def flaky(state):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise SourceUnavailable("temporary")
        real(state)

    container.nodes.specialists = flaky
    container.worker.run_pending()
    assert attempts["n"] == 3  # two transient failures, then success (FLOW-05)
    state = container.storage.runs.load(run.run_id)
    assert state.status is InvestigationStatus.WAITING_FOR_REVIEW
    assert len(state.messages) == len({m.idempotency_key for m in state.messages})  # no duplicates


def test_persistent_source_failure_ends_incomplete_not_failed(container, request_):
    def always_down(state):
        raise SourceUnavailable("down")

    container.nodes.specialists = always_down
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    container.worker.run_pending()
    state = container.storage.runs.load(run.run_id)
    assert state.status is InvestigationStatus.INCOMPLETE and "down" in state.stop_reason


def test_resubmitting_with_the_same_key_returns_the_same_run(container, request_):
    first = container.investigations.submit(SCIENTIST, "proj-1", request_, "same-key")
    second = container.investigations.submit(SCIENTIST, "proj-1", request_, "same-key")
    assert first.run_id == second.run_id
    assert container.worker.run_pending() == 1


def test_run_is_paused_at_the_review_interrupt_until_approval(container, request_):
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    container.worker.run_pending()
    snapshot = container.graph.get_state(thread(run.run_id))
    assert snapshot.next == ("await_review",)  # durably paused, nothing running
    report = container.investigations.report(SCIENTIST, run.run_id)
    container.investigations.approve(SCIENTIST, run.run_id, report.content_hash)
    assert container.graph.get_state(thread(run.run_id)).next == ()
    assert container.storage.runs.load(run.run_id).status is InvestigationStatus.COMPLETED


def test_repair_loop_is_bounded_at_two_rounds(container, request_):
    run = container.investigations.submit(SCIENTIST, "proj-1", request_, "k")
    container.worker.run_pending()
    values = container.graph.get_state(thread(run.run_id)).values
    assert 1 <= values["repair_round"] <= 3  # at most two repair rounds plus the closing pass
