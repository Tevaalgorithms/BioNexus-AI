import json
import subprocess
import sys
import zipfile

from bionexus.evals.run import REFERENCE, meets_ship_gates, run_all


def test_harness_ranks_systems_and_catches_ablation_loss():
    cases = json.loads(REFERENCE.read_text())["cases"]
    results = {name: rows[0] for name, rows in run_all(cases).items()}
    assert results["multi_agent"]["fabricated"] == 0
    assert results["multi_agent"]["excluded_leaks"] == 0
    assert results["multi_agent"]["contradiction_recall"] == 1.0
    assert results["deterministic_baseline"]["contradiction_recall"] == 0.0
    assert results["multi_agent_no_critic"]["recall_at_20"] < results["multi_agent"]["recall_at_20"]
    assert meets_ship_gates(results["multi_agent"])
    assert not meets_ship_gates(results["multi_agent_no_critic"])


def test_wheel_contains_migrations_and_fixtures(tmp_path):
    """Regression: the production image once shipped without its SQL migrations."""
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-q", "-w", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    names = zipfile.ZipFile(next(tmp_path.glob("bionexus-*.whl"))).namelist()
    assert any(n.endswith("storage/migrations/001_core.sql") for n in names)
    assert any(n.endswith("sources/fixtures/gwas.json") for n in names)
