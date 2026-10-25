"""HTTP layer. Thin by design: parse, authenticate, call a service, shape the response."""

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from bionexus.api.admin_routes import router as admin_router
from bionexus.api.deps import Caller
from bionexus.api.project_routes import router as project_router
from bionexus.api.run_routes import router as run_router
from bionexus.api.user_routes import router as user_router
from bionexus.container import Container
from bionexus.contracts.errors import BioNexusError
from bionexus.params import parameters

STATUS_BY_CODE = {
    "access_denied": 403,
    "not_found": 404,
    "conflict": 409,
    "invalid_request": 422,
    "invalid_transition": 409,
    "budget_exceeded": 429,
    "rate_limited": 429,
    "provisioning_failed": 502,
}

platform_router = APIRouter()


@platform_router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@platform_router.get("/me")
def me(principal: Caller) -> dict:
    return {
        "user_id": principal.user_id,
        "role": principal.role.value,
        "tenant_id": principal.tenant_id,
        "projects": sorted(principal.project_ids),
        "client": principal.client_kind.value,
    }


async def domain_error_response(_: Request, error: Exception) -> JSONResponse:
    code = getattr(error, "code", "internal_error")
    body = {"error": {"code": code, "message": str(error)}}
    return JSONResponse(body, STATUS_BY_CODE.get(code, 500))


def create_app(container: Container) -> FastAPI:
    docs = None if parameters().is_production() else "/docs"  # no public API docs in production
    app = FastAPI(
        title="BioNexus AI",
        docs_url=docs,
        redoc_url=None,
        openapi_url=None if docs is None else "/openapi.json",
    )
    app.state.container = container
    app.add_exception_handler(BioNexusError, domain_error_response)
    for router in (platform_router, project_router, run_router, admin_router, user_router):
        app.include_router(router)
    return app
