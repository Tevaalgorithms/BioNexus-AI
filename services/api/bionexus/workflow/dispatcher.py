"""Delivers routed messages to agents until no work remains, and merges what comes back."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor

from bionexus.agents.base import Agent, AgentResult, reply_to
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.messaging.router import MessageRouter
from bionexus.workflow.events import EventPublisher
from bionexus.workflow.state import RunState

MAX_PARALLEL_SPECIALISTS = 2  # SCOPE-05: two concurrent specialist calls per investigation


class Dispatcher:
    def __init__(
        self, agents: dict[AgentName, Agent], router: MessageRouter, events: EventPublisher
    ) -> None:
        self._agents = agents
        self._router = router
        self._events = events

    def run(self, state: RunState, initial: list[AgentMessage]) -> None:
        """Sequential delivery, used for repair rounds."""
        self._drain(state, initial)

    def run_parallel(self, state: RunState, initial: list[AgentMessage]) -> None:
        """Each initial task and its follow-up chain run on a bounded pool."""
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SPECIALISTS) as pool:
            futures = [pool.submit(self._drain, state, [message]) for message in initial]
            for future in futures:
                future.result()  # re-raises the first failure

    def _drain(self, state: RunState, initial: list[AgentMessage]) -> None:
        pending = deque(initial)
        while pending:
            message = pending.popleft()
            if self._accept(state, message):
                pending.extend(self._deliver(state, message))

    def _accept(self, state: RunState, message: AgentMessage) -> bool:
        with state.lock:
            accepted = self._router.accept(state, message)
        if accepted:
            self._events.handoff(message)
        return accepted

    def _deliver(self, state: RunState, message: AgentMessage) -> list[AgentMessage]:
        result = self._agents[message.recipient].handle(message, state)
        with state.lock:
            self._merge(state, result)
            self._router.accept(state, reply_to(message, result, MessageType.TASK_RESULT))
        return result.outgoing

    @staticmethod
    def _merge(state: RunState, result: AgentResult) -> None:
        state.add_evidence(result.evidence)
        state.excluded.extend(result.excluded)
