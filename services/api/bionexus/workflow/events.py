"""Sanitised progress events for the scientist timeline. No payloads or reasoning appear."""

from bionexus.contracts.messages import AgentMessage
from bionexus.storage.ports import EventStore


class EventPublisher:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def stage_completed(self, run_id: str, stage: str) -> None:
        self._store.append(run_id, "stage.completed", {"stage": stage})

    def handoff(self, message: AgentMessage) -> None:
        data = {
            "from": message.sender.value,
            "to": message.recipient.value,
            "type": message.type.value,
        }
        if message.payload.get("ask"):
            data["ask"] = message.payload["ask"]  # a challenge says what it asks for
        self._store.append(message.run_id, "agent.handoff", data)

    def status(self, run_id: str, status: str, reason: str | None = None) -> None:
        self._store.append(run_id, "run.status", {"status": status, "reason": reason})
