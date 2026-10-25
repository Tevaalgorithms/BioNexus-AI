"""A record of one model call, kept for cost reconciliation and the reproducibility manifest."""

from pydantic import BaseModel

from bionexus.contracts.messages import AgentName


class Invocation(BaseModel):
    agent: AgentName
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    fallback_reason: str | None = None
    cached: bool = False  # AO-5: answered from the cache; nothing was sent to a provider
