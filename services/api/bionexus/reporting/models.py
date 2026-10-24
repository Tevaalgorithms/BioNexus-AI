"""Report versions. A version is immutable; approval creates the next version with a parent link."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReportStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    run_id: str
    version: int
    status: ReportStatus
    parent_version: int | None
    markdown: str
    manifest: dict[str, object]
    content_hash: str
    approved_by: str | None = None
