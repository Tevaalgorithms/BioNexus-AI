"""The approved-model catalogue. Admins can add, deprecate and disable models at runtime.

Status rules (EVAL-10): only *active* models can be bound to an agent; a *deprecated* model keeps
serving runs already pinned to it; a *disabled* model serves nothing.
"""

import json
import re
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bionexus.contracts.errors import InvalidRequest
from bionexus.llm.clients import ProviderError
from bionexus.storage.catalog import ModelCatalog


class ModelStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class ModelSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    provider: str
    supports_structured_output: bool
    input_usd_per_million: float
    output_usd_per_million: float
    supports_temperature: bool = True
    api_key_secret: str | None = None  # parameter *name*, never the value
    price_verified_on: str | None = None
    status: ModelStatus = ModelStatus.ACTIVE
    created_by: str = "system"

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        total = (
            input_tokens * self.input_usd_per_million + output_tokens * self.output_usd_per_million
        )
        return total / 1_000_000


class ModelRegistry:
    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog

    def _find(self, model_id: str) -> ModelSpec:
        row = self._catalog.get(model_id)
        if row is None:
            raise InvalidRequest(f"Model '{model_id}' is not in the approved registry")
        return ModelSpec.model_validate(row)

    def get(self, model_id: str) -> ModelSpec:
        """For choosing a model in a binding: it must be active."""
        spec = self._find(model_id)
        if spec.status is not ModelStatus.ACTIVE:
            raise InvalidRequest(f"Model '{model_id}' is {spec.status}; choose an active model")
        return spec

    def get_for_call(self, model_id: str) -> ModelSpec:
        """For a pinned run: deprecated models still serve; disabled ones do not."""
        spec = self._find(model_id)
        if spec.status is ModelStatus.DISABLED:
            raise ProviderError(f"{model_id} is disabled by an administrator")
        return spec

    def all(self) -> list[ModelSpec]:
        return [ModelSpec.model_validate(row) for row in self._catalog.list()]

    def add(self, spec: ModelSpec) -> None:
        if self._catalog.get(spec.model_id) is not None:
            raise InvalidRequest(f"Model '{spec.model_id}' already exists; deprecate it instead")
        self._catalog.put(spec.model_dump(mode="json"))

    def set_status(self, model_id: str, status: ModelStatus) -> ModelSpec:
        updated = self._find(model_id).model_copy(update={"status": status})
        self._catalog.put(updated.model_dump(mode="json"))
        return updated

    def seed(self, specs: list[ModelSpec]) -> None:
        """Insert models that are missing; never overwrite what an admin has since changed."""
        for spec in specs:
            if self._catalog.get(spec.model_id) is None:
                self._catalog.put(spec.model_dump(mode="json"))


MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,99}$")


def model_problems(spec: ModelSpec, production: bool) -> list[str]:
    """Rules for admitting a model. Provider endpoints are fixed in code, never user-supplied."""
    from bionexus.llm.factory import ALL_PROVIDERS, PRODUCTION_PROVIDERS

    allowed = PRODUCTION_PROVIDERS if production else ALL_PROVIDERS
    checks = [
        (not MODEL_ID.match(spec.model_id), "model id has invalid characters"),
        (spec.provider not in allowed, f"provider must be one of {sorted(allowed)}"),
        *_paid_model_checks(spec),
    ]
    return [message for failed, message in checks if failed]


def _paid_model_checks(spec: ModelSpec) -> list[tuple[bool, str]]:
    if spec.provider == "fixture":
        return []
    from bionexus.params import parameters

    return [
        (not spec.api_key_secret, "an API key parameter name is required"),
        (
            bool(spec.api_key_secret) and not parameters().has(spec.api_key_secret or ""),
            "that API key parameter is not set in the parameter store",
        ),
        (
            spec.input_usd_per_million <= 0 or spec.output_usd_per_million <= 0,
            "prices must be positive (budgets depend on them)",
        ),
        (
            not _verified_date(spec.price_verified_on),
            "price_verified_on must be a past or current ISO date",
        ),
    ]


def _verified_date(value: str | None) -> bool:
    try:
        return date.fromisoformat(value or "") <= date.today()
    except ValueError:
        return False


def load_specs(path: Path) -> list[ModelSpec]:
    return specs_from_json(path.read_text())


def specs_from_json(text: str) -> list[ModelSpec]:
    """Seed list: reviewed JSON (a file locally, an SSM parameter in production), never user
    input (MODEL-07). Prices must be verified."""
    specs = [ModelSpec(**row) for row in json.loads(text)["models"]]
    for spec in specs:
        if spec.price_verified_on is None:
            raise InvalidRequest(f"Model '{spec.model_id}' has no verified price; budgets need it")
    return specs
