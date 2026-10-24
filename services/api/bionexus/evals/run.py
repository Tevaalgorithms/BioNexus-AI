"""`python -m bionexus.evals.run` compares baselines and ablations on the reference cases."""

import json
from pathlib import Path

from bionexus.evals import metrics as m
from bionexus.evals.systems import deterministic_baseline, multi_agent, single_agent_baseline

REFERENCE = Path(__file__).with_name("reference.json")
SHIP_GATES = {
    "citation_presence": 1.0,
    "entailment_proxy": 0.95,
    "recall_at_20": 0.90,
    "fabricated": 0,
}


def score(output, case: dict) -> dict:
    return {
        "citation_presence": m.citation_presence(output),
        "entailment_proxy": m.citation_entailment_proxy(output),
        "recall_at_20": m.essential_recall_at(output, case["essential_evidence"]),
        "fabricated": m.fabricated_identifiers(output),
        "contradiction_recall": m.contradiction_recall(output, case["known_contradictions"]),
        "excluded_leaks": m.excluded_leaks(output, case["must_exclude"]),
        "latency_s": round(output.latency_s, 3),
        "cost_usd": round(output.cost_usd, 6),
    }


def meets_ship_gates(row: dict) -> bool:
    """SHIP-07 thresholds. Only meaningful on a scientist-written locked set, not fixtures."""
    return (
        row["citation_presence"] >= SHIP_GATES["citation_presence"]
        and row["entailment_proxy"] >= SHIP_GATES["entailment_proxy"]
        and row["recall_at_20"] >= SHIP_GATES["recall_at_20"]
        and row["fabricated"] == SHIP_GATES["fabricated"]
    )


def run_all(cases: list[dict]) -> dict[str, list[dict]]:
    systems = {
        "deterministic_baseline": deterministic_baseline,
        "single_agent_baseline": single_agent_baseline,
        "multi_agent": multi_agent,
        "multi_agent_no_critic": lambda c: multi_agent(c, critic=False),
    }
    return {name: [score(fn(case), case) for case in cases] for name, fn in systems.items()}


def main() -> None:
    cases = json.loads(REFERENCE.read_text())["cases"]
    print(
        f"n = {len(cases)} case(s). SYNTHETIC fixtures: validates the harness, not real accuracy.\n"
    )
    for name, rows in run_all(cases).items():
        print(name)
        for row in rows:
            print("  ", row, "| gates:", meets_ship_gates(row))


if __name__ == "__main__":
    main()
