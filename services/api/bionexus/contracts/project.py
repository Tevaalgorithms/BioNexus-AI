"""A project is a private workspace (access boundary and memory scope), not a disease."""

import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field

SLUG = re.compile(r"[^a-z0-9]+")
MAX_PROJECTS_PER_TENANT = 50


def slugify(name: str) -> str:
    return SLUG.sub("-", name.lower()).strip("-")[:40]


class Project(BaseModel):
    project_id: str
    tenant_id: str
    name: str
    description: str = ""
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
