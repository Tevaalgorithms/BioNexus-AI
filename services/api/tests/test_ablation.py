"""The ablation tool runs the same question with each review step off and reports what changed."""

from datetime import date

from bionexus.config import Settings
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.evals.ablation import CONFIGS, render, run_all


def case() -> InvestigationRequest:
    return InvestigationRequest(
        disease="Crohn's disease",
        targets=("NOD2", "IL23R"),
        question="Compare NOD2 sensing and IL-23 signalling evidence.",
        evidence_cutoff=date(2026, 1, 1),
    )


def test_every_configuration_runs_to_review_and_reports_a_row():
    rows = run_all(case(), Settings())
    assert [r.config for r in rows] == list(CONFIGS)
    assert all(r.status == "waiting_for_review" for r in rows)


def test_a_step_that_is_switched_off_does_nothing():
    by_name = {r.config: r for r in run_all(case(), Settings())}
    assert by_name["no coverage review"].requests == 0
    assert by_name["no verifier"].withheld == 0 and by_name["no verifier"].unchecked == 0
    assert by_name["none of the three"].requests == 0
    assert (
        by_name["all steps"].unchecked > 0
    )  # the offline model cannot judge sentences, and says so


def test_the_table_has_one_line_per_configuration():
    text = render(run_all(case(), Settings()))
    assert len(text.splitlines()) == len(CONFIGS) + 2 and "all steps" in text
