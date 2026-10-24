"""Supervisor: deterministic planning (FLOW-02). Which specialists run is never left to a model."""

from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.messaging.envelope import new_message
from bionexus.workflow.state import RunState

INITIAL_SPECIALISTS = (AgentName.GENETICS, AgentName.LITERATURE, AgentName.CLINICAL)
# Pathways is not planned up front: genetics requests it for genetically supported targets only.


class SupervisorAgent(Agent):
    name: ClassVar[AgentName] = AgentName.SUPERVISOR
    skill_id: ClassVar[str] = "investigation.plan"

    def plan(self, state: RunState) -> list[AgentMessage]:
        return [self._task(state, specialist) for specialist in INITIAL_SPECIALISTS]

    def _task(self, state: RunState, recipient: AgentName) -> AgentMessage:
        return new_message(
            run_id=state.run_id,
            sender=self.name,
            recipient=recipient,
            kind=MessageType.TASK_REQUEST,
            payload={"targets": list(state.request.targets)},
        )

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        return AgentResult(abstained=True, assessment="The supervisor only plans.")
