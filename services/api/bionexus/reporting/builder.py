"""Builds the Markdown report and the reproducibility manifest from a finished run."""

import hashlib
import json

from bionexus.agents.skills import SkillRegistry
from bionexus.contracts.evidence import Stance
from bionexus.evidence.eligibility import accepted_evidence
from bionexus.evidence.matrix import MatrixRow, build_matrix
from bionexus.llm.release import ReleaseStore
from bionexus.reporting.models import Report, ReportStatus
from bionexus.reporting.next_steps import propose_next_steps
from bionexus.sources.registry import SourceRegistry
from bionexus.workflow.state import RunState

DISCLAIMER = "_Research use only. Not a treatment recommendation._"


class ReportBuilder:
    def __init__(
        self, releases: ReleaseStore, skills: SkillRegistry, sources: SourceRegistry
    ) -> None:
        self._releases = releases
        self._skills = skills
        self._sources = sources

    def build_draft(
        self, state: RunState, version: int = 1, parent_version: int | None = None
    ) -> Report:
        manifest = self._manifest(state)
        markdown = self._markdown(state)
        return Report(
            report_id=f"{state.run_id}-v{version}",
            run_id=state.run_id,
            version=version,
            status=ReportStatus.DRAFT,
            parent_version=parent_version,
            markdown=markdown,
            manifest=manifest,
            content_hash=content_hash(markdown, manifest),
        )

    def _manifest(self, state: RunState) -> dict[str, object]:
        release = self._releases.get(state.release_id)
        return {
            "run_id": state.run_id,
            "release_id": release.release_id,
            "skill_hashes": self._skills.hashes(release.skill_versions),
            "source_snapshots": self._sources.snapshots(),
            "evidence_digests": evidence_digests(state),
            "queries": {
                "disease": state.request.disease,
                "targets": list(state.request.targets),
                "evidence_cutoff": str(state.request.evidence_cutoff),
            },
            "model_calls": [i.model_dump() for i in state.invocations],
            "total_cost_usd": round(state.budget.spent_usd, 6),
            "evidence_ids": sorted(state.evidence),
            "ranked_evidence_ids": state.ranked_evidence_ids,
            "claim_ids": [c.claim_id for c in state.claims],
            "excluded": [e.model_dump() for e in state.excluded],
            "open_issues": [i.description for i in state.issues],
            "verifications": [v.model_dump(mode="json") for v in state.verifications],
            "conflict_analyses": [a.model_dump(mode="json") for a in state.analyses.values()],
            "handoffs": len(state.messages),
        }

    def _markdown(self, state: RunState) -> str:
        sections = [
            f"# Evidence dossier: {state.request.disease}\n"
            "**Status: DRAFT (not scientist approved)**",
            f"**Question:** {state.request.question}\n"
            f"**Evidence cutoff:** {state.request.evidence_cutoff}",
            self._matrix_section(state),
            self._findings_section(state),
            self._claims_section(state),
            f"## Summary\n{state.narrative}",
            self._experiments_section(state),
            self._limitations_section(state),
            self._graph_section(state),
            self._references_section(state),
            DISCLAIMER,
        ]
        return "\n\n".join(sections)

    @staticmethod
    def _rows(state: RunState) -> list[MatrixRow]:
        return build_matrix(accepted_evidence(list(state.evidence.values())))

    def _matrix_section(self, state: RunState) -> str:
        header = (
            "| Target | Supporting families | Opposing families | No direction |\n"
            "| --- | ---: | ---: | ---: |"
        )
        rows = [
            f"| {r.target} | {r.supporting_families} | {r.opposing_families} "
            f"| {r.unknown_families} |"
            for r in self._rows(state)
        ]
        return "## Evidence matrix\n" + "\n".join([header, *rows])

    def _findings_section(self, state: RunState) -> str:
        groups = {stance: [] for stance in Stance}
        for row in self._rows(state):
            groups[row.net_stance].append(row.target)
        labels = {
            Stance.SUPPORTS: "Supported",
            Stance.OPPOSES: "Opposed",
            Stance.UNKNOWN: "Unknown or mixed",
        }
        lines = [f"- **{labels[s]}:** {', '.join(t) or 'none'}" for s, t in groups.items()]
        return "## Findings by net direction\n" + "\n".join(lines)

    @staticmethod
    def _claims_section(state: RunState) -> str:
        lines = [f"- {c.text} [{', '.join(c.evidence_ids)}]" for c in state.claims]
        return "## Claims\n" + "\n".join(lines)

    @staticmethod
    def _experiments_section(state: RunState) -> str:
        steps = propose_next_steps(state.issues, list(state.evidence.values()))
        return "## Proposed next experiments\n" + "\n".join(f"- {s}" for s in steps or ["- None."])

    @staticmethod
    def _limitations_section(state: RunState) -> str:
        issues = [f"- {i.description}" for i in state.issues]
        excluded = [f"- Excluded {e.evidence_id}: {e.reason}" for e in state.excluded]
        notes = [*issues, *excluded, *ReportBuilder._review_notes(state)]
        return "## Limitations\n" + "\n".join(notes or ["- None recorded."])

    @staticmethod
    def _review_notes(state: RunState) -> list[str]:
        """What the critic explained and the verifier withheld. Model text is labelled."""
        notes = [
            f"- Conflict on {a.target} ({a.verdict.value}; model-written, unreviewed): "
            f"{a.explanation}"
            for a in state.analyses.values()
            if a.explanation
        ]
        withheld = [v for v in state.verifications if v.verdict.value == "unsupported"]
        notes += [
            f"- Withheld by the verifier ({v.subject}): {v.text} Reason: {v.reason}"
            for v in withheld
        ]
        unchecked = sum(v.verdict.value == "unchecked" for v in state.verifications)
        if unchecked:
            notes.append(f"- {unchecked} summary sentence(s) could not be checked and were kept.")
        return notes

    @staticmethod
    def _graph_section(state: RunState) -> str:
        lines = [f"- {edge}" for edge in state.graph_context[:20]]
        note = "Context edges (<= 2 hops). Connectivity is not evidence of mechanism."
        return "## Evidence graph context\n" + "\n".join([note, *lines])

    @staticmethod
    def _references_section(state: RunState) -> str:
        cited = sorted({e for c in state.claims for e in c.evidence_ids})
        lines = [
            f"- {i} ({state.evidence[i].source_id}, {state.evidence[i].study_family}): "
            f"{state.evidence[i].finding}"
            for i in cited
        ]
        return "## References\n" + "\n".join(lines)


def evidence_digests(state: RunState) -> dict[str, str]:
    """Per-source digest of the exact evidence used: reconstructs what the run saw."""
    by_source: dict[str, list[str]] = {}
    for record in state.evidence.values():
        by_source.setdefault(record.source, []).append(record.content_hash)
    return {
        s: hashlib.sha256("".join(sorted(h)).encode()).hexdigest() for s, h in by_source.items()
    }


def content_hash(markdown: str, manifest: dict[str, object]) -> str:
    body = markdown + json.dumps(manifest, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()
