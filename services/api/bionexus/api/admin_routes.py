"""Platform-admin routes. Every handler delegates to AdminService, which enforces the role."""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from bionexus.api.deps import AppContainer, Caller
from bionexus.contracts.messages import AgentName
from bionexus.llm.models import AgentBinding
from bionexus.llm.registry import ModelSpec, ModelStatus

router = APIRouter(prefix="/admin")


class BindingChange(BaseModel):
    binding: AgentBinding
    reason: str
    expected_revision: int


class ModelRegistration(BaseModel):
    model_id: str
    provider: str
    supports_structured_output: bool
    supports_temperature: bool = True
    api_key_secret: str | None = None
    input_usd_per_million: float
    output_usd_per_million: float
    price_verified_on: str | None = None


class StatusChange(BaseModel):
    status: ModelStatus
    reason: str


class EmergencyStop(BaseModel):
    enabled: bool
    reason: str


class Rollback(BaseModel):
    reason: str


@router.get("/release")
def active_release(principal: Caller, app: AppContainer) -> dict:
    return app.admin.active_release(principal).model_dump(mode="json")


@router.get("/releases")
def releases(principal: Caller, app: AppContainer) -> list[dict]:
    return [r.model_dump(mode="json") for r in app.admin.release_history(principal)]


@router.get("/models")
def models(principal: Caller, app: AppContainer) -> list[dict]:
    return app.admin.models(principal)


@router.post("/models", status_code=201)
def register_model(body: ModelRegistration, principal: Caller, app: AppContainer) -> dict:
    spec = ModelSpec(**body.model_dump())
    return app.admin.register_model(principal, spec).model_dump(mode="json")


@router.put("/models/{model_id}/status")
def set_model_status(
    model_id: str, body: StatusChange, principal: Caller, app: AppContainer
) -> dict:
    updated = app.admin.set_model_status(principal, model_id, body.status, body.reason)
    return updated.model_dump(mode="json")


@router.post("/models/{model_id}/smoke-test")
def smoke(model_id: str, principal: Caller, app: AppContainer) -> dict:
    return app.admin.smoke_test(principal, model_id)


@router.post("/agents/{agent}/binding/validate")
def validate(agent: AgentName, body: BindingChange, principal: Caller, app: AppContainer) -> dict:
    result = app.admin.validate_binding(principal, agent, body.binding)
    return {"valid": result.valid, "problems": result.problems, "changes": result.changes}


@router.post("/agents/{agent}/binding/evaluate")
def evaluate(agent: AgentName, body: BindingChange, principal: Caller, app: AppContainer) -> dict:
    return app.admin.evaluate_binding(principal, agent, body.binding, body.reason)


@router.put("/agents/{agent}/binding")
def rebind(agent: AgentName, body: BindingChange, principal: Caller, app: AppContainer) -> dict:
    release = app.admin.rebind_agent(
        principal, agent, body.binding, body.reason, body.expected_revision
    )
    return release.model_dump(mode="json")


@router.post("/releases/{release_id}/rollback")
def rollback(release_id: str, body: Rollback, principal: Caller, app: AppContainer) -> dict:
    return app.admin.rollback(principal, release_id, body.reason).model_dump(mode="json")


@router.get("/usage")
def usage(principal: Caller, app: AppContainer) -> dict:
    return app.admin.usage(principal)


@router.get("/health")
def health(principal: Caller, app: AppContainer) -> dict:
    return app.admin.health(principal)


@router.put("/emergency-stop")
def emergency_stop(body: EmergencyStop, principal: Caller, app: AppContainer) -> dict:
    return {"enabled": app.admin.set_emergency_stop(principal, body.enabled, body.reason)}


@router.get("/audit")
def audit(principal: Caller, app: AppContainer) -> list[dict]:
    return app.admin.audit_events(principal)


@router.get("/skills")
def skills(principal: Caller, app: AppContainer) -> dict:
    return app.admin.skills(principal)


@router.get("/sources")
def sources(principal: Caller, app: AppContainer) -> list[dict]:
    return app.admin.sources(principal)


@router.post("/sources/{name}/check")
def check_source(name: str, principal: Caller, app: AppContainer) -> dict:
    return app.admin.check_source(principal, name)


@router.get("/metrics")
def metrics(principal: Caller, app: AppContainer) -> Response:
    return Response(app.admin.metrics_text(principal), media_type="text/plain")
