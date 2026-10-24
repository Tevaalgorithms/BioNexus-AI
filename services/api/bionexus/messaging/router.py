"""The only path between agents: an allowlist with depth and volume limits (A2A-05, A2A-09)."""

from bionexus.contracts.errors import RouteRejected
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.workflow.state import RunState

A = AgentName
SPECIALISTS = frozenset({A.GENETICS, A.LITERATURE, A.PATHWAYS, A.CLINICAL})

ALLOWED_ROUTES: dict[AgentName, frozenset[AgentName]] = {
    A.SUPERVISOR: SPECIALISTS | {A.CRITIC, A.SYNTHESIZER},
    A.GENETICS: frozenset({A.PATHWAYS}),
    A.CRITIC: SPECIALISTS,
}
REPLY_TYPES = frozenset({MessageType.TASK_RESULT, MessageType.TASK_FAILED})

MAX_DEPTH = 3
MAX_MESSAGES_PER_RUN = 40


class MessageRouter:
    def accept(self, state: RunState, message: AgentMessage) -> bool:
        """Validate and persist a message. Returns False for a duplicate delivery."""
        if self._is_duplicate(state, message):
            return False
        self._check_limits(state, message)
        self._check_route(state, message)
        state.messages.append(message)
        return True

    @staticmethod
    def _is_duplicate(state: RunState, message: AgentMessage) -> bool:
        return any(m.idempotency_key == message.idempotency_key for m in state.messages)

    @staticmethod
    def _check_limits(state: RunState, message: AgentMessage) -> None:
        if message.depth > MAX_DEPTH:
            raise RouteRejected("Maximum handoff depth exceeded")
        if len(state.messages) >= MAX_MESSAGES_PER_RUN:
            raise RouteRejected("Message limit for this run reached")

    def _check_route(self, state: RunState, message: AgentMessage) -> None:
        if message.type in REPLY_TYPES:
            self._check_reply(state, message)
        elif message.recipient not in ALLOWED_ROUTES.get(message.sender, frozenset()):
            raise RouteRejected(f"{message.sender} may not message {message.recipient}")

    @staticmethod
    def _check_reply(state: RunState, message: AgentMessage) -> None:
        parents = [m for m in state.messages if m.message_id == message.parent_id]
        if not parents or parents[0].sender != message.recipient:
            raise RouteRejected("A reply must answer a message addressed to the sender")
