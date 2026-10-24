"""Builds well-formed messages. Ids and lineage are set here, never by agents."""

import hashlib
import json
import uuid

from bionexus.contracts.messages import AgentMessage, AgentName, MessageType


def _idempotency_key(
    sender: AgentName, recipient: AgentName, kind: MessageType, payload: dict[str, object]
) -> str:
    body = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{sender}|{recipient}|{kind}|{body}".encode()).hexdigest()[:16]


def new_message(
    *,
    run_id: str,
    sender: AgentName,
    recipient: AgentName,
    kind: MessageType,
    payload: dict[str, object],
    parent: AgentMessage | None = None,
    evidence_ids: tuple[str, ...] = (),
) -> AgentMessage:
    message_id = uuid.uuid4().hex
    return AgentMessage(
        message_id=message_id,
        correlation_id=parent.correlation_id if parent else message_id,
        parent_id=parent.message_id if parent else None,
        run_id=run_id,
        sender=sender,
        recipient=recipient,
        type=kind,
        payload=payload,
        evidence_ids=evidence_ids,
        depth=parent.depth + 1 if parent else 0,
        idempotency_key=_idempotency_key(sender, recipient, kind, payload),
    )
