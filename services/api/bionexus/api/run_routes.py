"""Scientist routes: submit, monitor, review, revise, approve, export."""

import asyncio
import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Header, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from bionexus.api.deps import AppContainer, Caller
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.presentation import run_detail, run_summary

router = APIRouter()

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
POLL_SECONDS = 0.5
HEARTBEAT_EVERY = 30  # idle polls between heartbeats; keeps proxies from closing the stream


class ApproveRequest(BaseModel):
    report_hash: str


class ExcludeRequest(BaseModel):
    evidence_ids: list[str]
    reason: str


@router.post("/projects/{project_id}/investigations", status_code=202)
def submit(
    project_id: str,
    request: InvestigationRequest,
    background: BackgroundTasks,
    idempotency_key: Annotated[str, Header()],
    principal: Caller,
    app: AppContainer,
) -> dict[str, str]:
    state = app.investigations.submit(principal, project_id, request, idempotency_key)
    if app.inline_worker:  # production runs a separate worker service
        background.add_task(app.worker.run_pending)
    return {"run_id": state.run_id, "status": state.status}


@router.get("/meta")
def meta(principal: Caller, app: AppContainer) -> dict:
    """How this installation is running (demo fixtures or live databases; demo or real models)."""
    return app.meta()


@router.get("/projects/{project_id}/investigations")
def history(project_id: str, principal: Caller, app: AppContainer) -> list[dict]:
    return [run_summary(s) for s in app.investigations.history(principal, project_id)]


@router.get("/investigations/{run_id}")
def get_investigation(run_id: str, principal: Caller, app: AppContainer) -> dict:
    return run_summary(app.investigations.get(principal, run_id))


@router.get("/investigations/{run_id}/detail")
def detail(run_id: str, principal: Caller, app: AppContainer) -> dict:
    return run_detail(app.investigations.get(principal, run_id))


@router.get("/investigations/{run_id}/messages")
def messages(run_id: str, principal: Caller, app: AppContainer) -> list[dict]:
    """Authorised audit view: full envelopes, still without any model reasoning."""
    state = app.investigations.get(principal, run_id)
    return [m.model_dump(mode="json") for m in state.messages]


@router.post("/investigations/{run_id}/cancel", status_code=202)
def cancel(run_id: str, principal: Caller, app: AppContainer) -> dict:
    return run_summary(app.investigations.cancel(principal, run_id))


@router.get("/investigations/{run_id}/events")
def events(run_id: str, principal: Caller, app: AppContainer, after: int = 0) -> list[dict]:
    """Polling fallback for the event stream."""
    return [e.model_dump() for e in app.investigations.events(principal, run_id, after)]


@router.get("/investigations/{run_id}/events/stream")
def stream(
    run_id: str,
    principal: Caller,
    app: AppContainer,
    last_event_id: Annotated[int, Header()] = 0,
) -> StreamingResponse:
    app.investigations.get(principal, run_id)  # authorise before streaming
    body = event_stream(app, principal, run_id, last_event_id)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(body, media_type="text/event-stream", headers=headers)


@router.get("/investigations/{run_id}/report")
def get_report(run_id: str, principal: Caller, app: AppContainer) -> dict:
    return app.investigations.report(principal, run_id).model_dump()


@router.get("/investigations/{run_id}/report/versions")
def versions(run_id: str, principal: Caller, app: AppContainer) -> list[dict]:
    return [
        {
            "version": r.version,
            "status": r.status.value,
            "parent_version": r.parent_version,
            "content_hash": r.content_hash,
            "approved_by": r.approved_by,
        }
        for r in app.investigations.report_versions(principal, run_id)
    ]


@router.get("/investigations/{run_id}/report/export")
def export(
    run_id: str, principal: Caller, app: AppContainer, fmt: Literal["md", "docx", "json"] = "md"
) -> Response:
    if fmt == "docx":
        return Response(app.investigations.export_docx(principal, run_id), media_type=DOCX_TYPE)
    report = app.investigations.report(principal, run_id)
    if fmt == "json":
        manifest = json.dumps(report.manifest, indent=2, default=str)
        return Response(manifest, media_type="application/json")
    return Response(report.markdown, media_type="text/markdown")


@router.post("/investigations/{run_id}/report/exclusions")
def exclude(run_id: str, body: ExcludeRequest, principal: Caller, app: AppContainer) -> dict:
    report = app.investigations.exclude_evidence(principal, run_id, body.evidence_ids, body.reason)
    return report.model_dump()


@router.post("/investigations/{run_id}/report/approve")
def approve(run_id: str, body: ApproveRequest, principal: Caller, app: AppContainer) -> dict:
    return app.investigations.approve(principal, run_id, body.report_hash).model_dump()


def sse_frame(event) -> str:
    return f"id: {event.seq}\nevent: {event.kind}\ndata: {json.dumps(event.data)}\n\n"


def heartbeat_due(idle_polls: int) -> bool:
    return idle_polls > 0 and idle_polls % HEARTBEAT_EVERY == 0


async def event_stream(app, principal, run_id: str, last_id: int):
    """Server-sent events with replay from `Last-Event-ID` and periodic heartbeats."""
    idle_polls = 0
    while True:
        fresh = app.investigations.events(principal, run_id, last_id)
        for event in fresh:
            last_id = event.seq
            yield sse_frame(event)
        if not fresh and app.investigations.is_finished(principal, run_id):
            yield "event: end\ndata: {}\n\n"
            return
        idle_polls = 0 if fresh else idle_polls + 1
        if heartbeat_due(idle_polls):
            yield ": heartbeat\n\n"
        await asyncio.sleep(POLL_SECONDS)
