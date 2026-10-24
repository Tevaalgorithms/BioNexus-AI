"""Versioned skill contracts. Only approved, immutable versions load; every load is hashed."""

import hashlib
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bionexus.contracts.errors import InvalidRequest, NotFound

DEFAULT_SKILLS_DIR = Path(
    os.getenv("BIONEXUS_SKILLS_DIR") or Path(__file__).resolve().parents[4] / "skills"
)


class Skill(BaseModel):
    model_config = ConfigDict(frozen=True)

    skill_id: str
    version: str
    owner: str
    approved: bool
    instructions: str
    interpretation_limits: str
    abstain_when: str
    content_hash: str


class SkillRegistry:
    def __init__(self, root: Path = DEFAULT_SKILLS_DIR) -> None:
        self._root = root

    def get(self, skill_id: str, version: str) -> Skill:
        path = self._root / skill_id / version / "skill.json"
        if not path.is_file():
            raise NotFound(f"Skill {skill_id}@{version} does not exist")
        raw = path.read_bytes()
        skill = Skill(content_hash=hashlib.sha256(raw).hexdigest(), **json.loads(raw))
        if not skill.approved:
            raise InvalidRequest(f"Skill {skill_id}@{version} is not approved")
        return skill

    def describe(self, versions: dict[str, str]) -> list[dict]:
        """Everything an administrator needs to inspect each pinned skill."""
        return [self.get(sid, v).model_dump() for sid, v in versions.items()]

    def hashes(self, versions: dict[str, str]) -> dict[str, str]:
        return {sid: self.get(sid, v).content_hash for sid, v in versions.items()}
