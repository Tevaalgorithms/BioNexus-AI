"""Runs the investigation graph and turns its outcome into an honest run status."""

from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from bionexus.contracts.errors import RecoverableRunError, RunCancelled
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.observability import log_event
from bionexus.storage.ports import RunStore
from bionexus.workflow.events import EventPublisher
from bionexus.workflow.state import RunState


def thread(run_id: str) -> dict:
    """One durable LangGraph thread per investigation."""
    return {"configurable": {"thread_id": run_id}}


class RunExecutor:
    def __init__(self, graph: CompiledStateGraph, runs: RunStore, events: EventPublisher) -> None:
        self._graph = graph
        self._runs = runs
        self._events = events

    def execute(self, run_id: str) -> RunState:
        state = self._runs.load(run_id)
        self._start(state)
        try:
            result = self._graph.invoke(self._graph_input(run_id), thread(run_id))
            if "__interrupt__" in result:  # paused at the human-review step
                state = self._runs.load(run_id)
                state.transition(InvestigationStatus.WAITING_FOR_REVIEW)
        except RunCancelled as error:
            state = self._stopped(run_id, InvestigationStatus.CANCELLED, str(error))
        except RecoverableRunError as error:
            state = self._stopped(run_id, InvestigationStatus.INCOMPLETE, str(error))
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            state = self._stopped(run_id, InvestigationStatus.FAILED, reason)
        self._finish(state)
        return state

    def resume_after_review(self, run_id: str, reviewer: str) -> None:
        """Called once a scientist has approved: the paused graph continues to `complete`."""
        self._graph.invoke(Command(resume={"reviewer": reviewer}), thread(run_id))
        self._events.status(run_id, InvestigationStatus.COMPLETED.value, None)

    def _graph_input(self, run_id: str) -> dict[str, Any] | None:
        """A fresh thread starts at the beginning; an existing one resumes from its checkpoint."""
        if self._graph.get_state(thread(run_id)).created_at is not None:
            return None
        return {"run_id": run_id, "repair_round": 0}

    def _start(self, state: RunState) -> None:
        """A run found already RUNNING is crash recovery: resume it, do not restart it."""
        if state.status is InvestigationStatus.QUEUED:
            state.transition(InvestigationStatus.RUNNING)
            self._runs.save(state)

    def _stopped(self, run_id: str, status: InvestigationStatus, reason: str) -> RunState:
        state = self._runs.load(run_id)  # nodes saved their progress; add only the outcome
        state.stop_reason = reason
        state.transition(status)
        return state

    def _finish(self, state: RunState) -> None:
        self._runs.save(state)
        self._events.status(state.run_id, state.status.value, state.stop_reason)
        log_event(
            "run.finished",
            run_id=state.run_id,
            tenant=state.tenant_id,
            status=state.status.value,
            cost_usd=round(state.budget.spent_usd, 6),
        )
