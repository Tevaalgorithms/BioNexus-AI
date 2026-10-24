"""Offline demo: `python -m bionexus.cli.demo` runs the Crohn's pilot scenario end to end."""

from datetime import date

from bionexus.container import build_container
from bionexus.contracts.identity import Principal, Role
from bionexus.contracts.investigation import InvestigationRequest

SCIENTIST = Principal(
    user_id="demo-scientist",
    role=Role.SCIENTIST,
    tenant_id="demo-org",
    project_ids=frozenset({"crohns"}),
)


def main() -> None:
    app = build_container({"demo": SCIENTIST})
    request = InvestigationRequest(
        disease="Crohn's disease",
        targets=("NOD2", "IL23R"),
        question="Compare NOD2-related sensing and IL-23 signalling evidence.",
        evidence_cutoff=date(2026, 1, 1),
    )
    run = app.investigations.submit(SCIENTIST, "crohns", request, "demo-1")
    app.worker.run_pending()
    state = app.investigations.get(SCIENTIST, run.run_id)
    print(
        f"status={state.status} messages={len(state.messages)} cost=${state.budget.spent_usd:.6f}\n"
    )
    print(app.investigations.report(SCIENTIST, run.run_id).markdown)


if __name__ == "__main__":
    main()
