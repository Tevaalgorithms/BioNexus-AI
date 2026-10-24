"""Release value objects (kept free of storage so adapters can import them)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from bionexus.contracts.messages import AgentName


class AgentBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    fallback_model_id: str | None = None
    max_output_tokens: int = 400
    temperature: float | None = None

    def model_chain(self) -> list[str]:
        return [self.model_id, *([self.fallback_model_id] if self.fallback_model_id else [])]


class ConfigRelease(BaseModel):
    model_config = ConfigDict(frozen=True)

    release_id: str
    revision: int
    bindings: dict[AgentName, AgentBinding]
    skill_versions: dict[str, str]
    created_by: str
    reason: str
    parent_id: str | None
    created_at: datetime
