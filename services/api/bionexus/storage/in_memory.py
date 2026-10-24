"""In-memory adapters: used by unit tests and the offline demo. Same contracts as PostgreSQL."""

import uuid
from datetime import date, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver

from bionexus.contracts.errors import Conflict, NotFound
from bionexus.contracts.evidence import EvidenceRecord, ReviewState
from bionexus.contracts.identity import Principal
from bionexus.contracts.project import Project
from bionexus.evidence.eligibility import exclusion_reason
from bionexus.jobs.models import Job
from bionexus.llm.models import ConfigRelease
from bionexus.reporting.models import Report
from bionexus.retrieval.in_memory import InMemoryRetrieval
from bionexus.storage.catalog import InMemoryCatalog
from bionexus.storage.models import AuditEvent, RunEvent
from bionexus.storage.ports import Storage
from bionexus.workflow.state import RunState

LEASE_SECONDS = 300
MAX_ATTEMPTS = 3


class InMemoryRuns:
    """Stores runs as JSON, proving state is serialisable exactly as the database does."""

    def __init__(self) -> None:
        self._runs: dict[str, str] = {}
        self._cancelled: set[str] = set()

    def request_cancel(self, run_id: str) -> None:
        self._cancelled.add(run_id)

    def cancel_requested(self, run_id: str) -> bool:
        return run_id in self._cancelled

    def save(self, state: RunState) -> None:
        self._runs[state.run_id] = state.model_dump_json()

    def load(self, run_id: str) -> RunState:
        raw = self._runs.get(run_id)
        if raw is None:
            raise NotFound(f"Run '{run_id}' does not exist")
        return RunState.model_validate_json(raw)

    def list_all(self) -> list[RunState]:
        return [RunState.model_validate_json(raw) for raw in self._runs.values()]

    def list_for_project(self, tenant_id: str, project_id: str) -> list[RunState]:
        return [
            s for s in self.list_all() if (s.tenant_id, s.project_id) == (tenant_id, project_id)
        ]


class InMemoryJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def find(self, idempotency_key: str) -> Job | None:
        return next((j for j in self._jobs.values() if j.idempotency_key == idempotency_key), None)

    def enqueue(self, run_id: str, idempotency_key: str) -> Job:
        job = Job(job_id=uuid.uuid4().hex, run_id=run_id, idempotency_key=idempotency_key)
        self._jobs[job.job_id] = job
        return job

    def lease(self, now: datetime) -> Job | None:
        for job in self._jobs.values():
            if self._is_available(job, now):
                job.attempts += 1
                job.lease_expires = now + timedelta(seconds=LEASE_SECONDS)
                return job
        return None

    @staticmethod
    def _is_available(job: Job, now: datetime) -> bool:
        lease_free = job.lease_expires is None or job.lease_expires <= now
        return not job.done and lease_free and job.attempts < MAX_ATTEMPTS

    def complete(self, job: Job) -> None:
        job.done = True
        job.lease_expires = None

    def depth(self) -> int:
        return sum(1 for job in self._jobs.values() if not job.done)


class InMemoryReports:
    """Saving a draft twice returns the first one, so finalisation is idempotent."""

    def __init__(self) -> None:
        self._versions: dict[str, list[Report]] = {}

    def save_draft(self, report: Report) -> Report:
        versions = self._versions.setdefault(report.run_id, [])
        if versions:
            return versions[0]
        versions.append(report)
        return report

    def add_version(self, report: Report) -> None:
        self._versions[report.run_id].append(report)

    def latest(self, run_id: str) -> Report:
        versions = self._versions.get(run_id)
        if not versions:
            raise NotFound(f"No report exists for run '{run_id}'")
        return versions[-1]

    def versions(self, run_id: str) -> list[Report]:
        return list(self._versions.get(run_id, []))


class InMemoryAudit:
    """Append-only: there is deliberately no update or delete."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, actor: str, action: str, detail: str) -> None:
        self._events.append(AuditEvent(actor=actor, action=action, detail=detail))

    def events(self) -> list[AuditEvent]:
        return list(self._events)


class InMemoryMemory:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, EvidenceRecord]] = {}

    def promote(self, tenant_id: str, project_id: str, records: list[EvidenceRecord]) -> None:
        scope = self._items.setdefault((tenant_id, project_id), {})
        for record in records:
            reviewed = record.model_copy(update={"review_state": ReviewState.REVIEWED})
            scope[record.evidence_id] = reviewed

    def exclude(self, tenant_id: str, project_id: str, evidence_id: str) -> None:
        scope = self._items.get((tenant_id, project_id), {})
        if evidence_id in scope:
            excluded = {"review_state": ReviewState.EXCLUDED}
            scope[evidence_id] = scope[evidence_id].model_copy(update=excluded)

    def recall(
        self, tenant_id: str, project_id: str, targets: tuple[str, ...], cutoff: date
    ) -> list[EvidenceRecord]:
        scope = self._items.get((tenant_id, project_id), {})
        return [
            r for r in scope.values() if r.target in targets and exclusion_reason(r, cutoff) is None
        ]


class InMemoryReleases:
    def __init__(self) -> None:
        self._releases: dict[str, ConfigRelease] = {}
        self._active_id = ""

    def add(self, release: ConfigRelease, *, activate: bool) -> None:
        self._releases[release.release_id] = release
        if activate:
            self._active_id = release.release_id

    def get(self, release_id: str) -> ConfigRelease | None:
        return self._releases.get(release_id)

    def active(self) -> ConfigRelease:
        return self._releases[self._active_id]

    def history(self) -> list[ConfigRelease]:
        return sorted(self._releases.values(), key=lambda r: r.revision)


class InMemoryUsers:
    """Directory of invited users keyed by identity-provider subject."""

    def __init__(self, principals: dict[str, Principal] | None = None) -> None:
        self._principals = dict(principals or {})
        self._revoked: dict[str, datetime] = {}

    def find_by_subject(self, subject: str) -> Principal | None:
        return self._principals.get(subject)

    def find_by_user_id(self, user_id: str) -> Principal | None:
        return next((p for p in self._principals.values() if p.user_id == user_id), None)

    def revoked_before(self, subject: str) -> datetime | None:
        return self._revoked.get(subject)

    def revoke_sessions(self, subject: str, at: datetime) -> None:
        self._revoked[subject] = at

    def upsert(self, subject: str, principal: Principal) -> None:
        self._principals[subject] = principal

    def disable(self, subject: str) -> None:
        self._principals.pop(subject, None)


class InMemoryEvents:
    def __init__(self) -> None:
        self._events: list[RunEvent] = []

    def append(self, run_id: str, kind: str, data: dict) -> RunEvent:
        seq = len(self._events) + 1  # globally monotonic, like the SQL sequence
        event = RunEvent(run_id=run_id, seq=seq, kind=kind, data=data)
        self._events.append(event)
        return event

    def since(self, run_id: str, after_seq: int) -> list[RunEvent]:
        return [e for e in self._events if e.run_id == run_id and e.seq > after_seq]


class InMemoryProjects:
    def __init__(self) -> None:
        self._projects: dict[tuple[str, str], Project] = {}
        self._members: dict[tuple[str, str], set[str]] = {}

    def add(self, project: Project) -> None:
        key = (project.tenant_id, project.project_id)
        if key in self._projects:
            raise Conflict(f"A project named '{project.project_id}' already exists")
        self._projects[key] = project

    def all(self, tenant_id: str) -> list[Project]:
        return [p for (t, _), p in self._projects.items() if t == tenant_id]

    def count(self, tenant_id: str) -> int:
        return len(self.list(tenant_id))

    def add_member(self, tenant_id: str, project_id: str, user_id: str) -> None:
        self._members.setdefault((tenant_id, project_id), set()).add(user_id)

    def members(self, tenant_id: str, project_id: str) -> list[str]:
        return sorted(self._members.get((tenant_id, project_id), set()))

    def project_ids_for(self, tenant_id: str, user_id: str) -> frozenset[str]:
        return frozenset(
            p for (t, p), users in self._members.items() if t == tenant_id and user_id in users
        )


class InMemoryFlags:
    def __init__(self) -> None:
        self._flags: set[str] = set()

    def is_set(self, name: str) -> bool:
        return name in self._flags

    def set(self, name: str, value: bool) -> None:
        (self._flags.add if value else self._flags.discard)(name)


def in_memory_storage(principals: dict[str, Principal] | None = None) -> Storage:
    return Storage(
        runs=InMemoryRuns(),
        jobs=InMemoryJobs(),
        reports=InMemoryReports(),
        audit=InMemoryAudit(),
        memory=InMemoryMemory(),
        releases=InMemoryReleases(),
        users=InMemoryUsers(principals),
        events=InMemoryEvents(),
        flags=InMemoryFlags(),
        catalog=InMemoryCatalog(),
        checkpointer=InMemorySaver(),
        projects=InMemoryProjects(),
        retrieval=InMemoryRetrieval(),
    )
