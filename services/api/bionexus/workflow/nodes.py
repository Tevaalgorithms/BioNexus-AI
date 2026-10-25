"""The work done at each step of the investigation graph.

LangGraph (workflow/graph.py) decides *which step runs next*, retries, pauses for review and
resumes after a crash. These methods do the actual work. The domain state (`RunState`) stays in our
own database: every step loads it, changes it, and saves it, so the API and UI always see the same
truth and the graph checkpoint only needs to remember where the run is.
"""

from bionexus.agents.critic import CriticAgent, find_issues
from bionexus.agents.supervisor import SupervisorAgent
from bionexus.agents.synthesizer import SynthesizerAgent
from bionexus.agents.verifier import apply_verifications
from bionexus.contracts.errors import InvalidRequest, NoEvidenceFound, RunCancelled
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.evidence.eligibility import accepted_evidence
from bionexus.messaging.envelope import new_message
from bionexus.reporting.builder import ReportBuilder
from bionexus.retrieval.models import Scope
from bionexus.retrieval.service import RetrievalService
from bionexus.storage.ports import AuditStore, MemoryStore, ReportRepository, RunStore
from bionexus.workflow.dispatcher import Dispatcher
from bionexus.workflow.events import EventPublisher
from bionexus.workflow.state import RunState

MAX_REPAIR_ROUNDS = 2


class InvestigationNodes:
    def __init__(
        self,
        *,
        supervisor: SupervisorAgent,
        critic: CriticAgent,
        synthesizer: SynthesizerAgent,
        dispatcher: Dispatcher,
        memory: MemoryStore,
        builder: ReportBuilder,
        reports: ReportRepository,
        runs: RunStore,
        events: EventPublisher,
        retrieval: RetrievalService,
        audit: AuditStore,
    ) -> None:
        self._supervisor = supervisor
        self._critic = critic
        self._synthesizer = synthesizer
        self._dispatcher = dispatcher
        self._memory = memory
        self._builder = builder
        self._reports = reports
        self._runs = runs
        self._events = events
        self._retrieval = retrieval
        self._audit = audit

    def load(self, run_id: str) -> RunState:
        return self._runs.load(run_id)

    def ensure_not_cancelled(self, run_id: str) -> None:
        if self._runs.cancel_requested(run_id):
            raise RunCancelled("Cancelled by the scientist")

    def done(self, state: RunState, stage: str) -> None:
        """Persist the domain state and tell the activity timeline the step finished."""
        self._runs.save(state)
        self._events.stage_completed(state.run_id, stage)

    def scope(self, state: RunState) -> None:
        if not state.request.targets:
            raise InvalidRequest("At least one target is required")

    def recall_memory(self, state: RunState) -> None:
        recalled = self._memory.recall(
            state.tenant_id, state.project_id, state.request.targets, state.request.evidence_cutoff
        )
        state.add_evidence(recalled)

    def specialists(self, state: RunState) -> None:
        self._dispatcher.run_parallel(state, self._supervisor.plan(state))
        if not state.evidence:
            raise NoEvidenceFound("No eligible evidence found; check the disease and target names")

    def needs_repair(self, state: RunState, round_number: int) -> bool:
        """The graph's loop condition: something is fixable and the round budget remains."""
        return round_number < MAX_REPAIR_ROUNDS and self._critic.has_work(state)

    def critique_round(self, state: RunState, round_number: int) -> None:
        """One critic pass: challenge the specialists, then re-assess what is still open."""
        if self.needs_repair(state, round_number):
            self._dispatcher.run(state, [self._critic_task(state, round_number)])
        state.issues = find_issues(list(state.evidence.values()))

    @staticmethod
    def _critic_task(state: RunState, round_number: int) -> AgentMessage:
        return InvestigationNodes._task(state, AgentName.CRITIC, {"repair_round": round_number})

    @staticmethod
    def _task(state: RunState, recipient: AgentName, payload: dict) -> AgentMessage:
        """A task from the supervisor, so the handoff is recorded like any other."""
        return new_message(
            run_id=state.run_id,
            sender=AgentName.SUPERVISOR,
            recipient=recipient,
            kind=MessageType.TASK_REQUEST,
            payload=payload,
        )

    def coverage(self, state: RunState) -> None:
        """The planner reviews what was found and may ask specialists to search again."""
        self._dispatcher.run(state, [self._task(state, AgentName.PLANNER, {})])

    def retrieve(self, state: RunState) -> None:
        """Index accepted evidence, rank it for the question, and gather bounded graph context."""
        scope = Scope(
            tenant_id=state.tenant_id,
            project_id=state.project_id,
            run_id=state.run_id,
            cutoff=state.request.evidence_cutoff,
        )
        records = accepted_evidence(list(state.evidence.values()))
        self._retrieval.index(scope, records, state.request.disease)
        query = f"{state.request.question} {' '.join(state.request.targets)}"
        state.ranked_evidence_ids = [h.evidence_id for h in self._retrieval.search(scope, query)]
        edges = self._retrieval.expand(scope, list(state.request.targets))
        state.graph_context = [
            f"{e.subject} -{e.relation}-> {e.object} [{e.evidence_id}]" for e in edges
        ]

    def synthesize(self, state: RunState) -> None:
        synthesis = self._synthesizer.write(state)
        known = set(state.evidence)
        for claim in synthesis.claims:
            if not set(claim.evidence_ids) <= known:
                raise InvalidRequest(f"{claim.claim_id} cites unknown evidence")
        state.claims = synthesis.claims
        state.narrative = synthesis.narrative

    def verify(self, state: RunState) -> None:
        """The verifier checks the findings; whatever the evidence does not support is withheld."""
        state.verifications = []
        self._dispatcher.run(state, [self._task(state, AgentName.VERIFIER, {})])
        apply_verifications(state)

    def finalize(self, state: RunState) -> None:
        report = self._reports.save_draft(self._builder.build_draft(state))
        state.report_id = report.report_id

    def complete(self, state: RunState, reviewer: str) -> None:
        """After human approval: close the run and promote reviewed evidence to project memory."""
        if state.status is InvestigationStatus.COMPLETED:
            return  # idempotent: a retried resume must not promote twice
        state.transition(InvestigationStatus.COMPLETED)
        self._memory.promote(state.tenant_id, state.project_id, list(state.evidence.values()))
        self._audit.record(reviewer, "report.approved", state.report_id or state.run_id)
