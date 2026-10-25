"""`python -m bionexus.evals.ablation`: the same question, with each review step switched off.

It runs one investigation per configuration and prints what each step changed: how much evidence was
found, what was requested, explained and withheld, and what it cost. It does NOT score accuracy.
That needs a scientist-written question set with known answers; this only shows behaviour.

Offline (no arguments) it uses the placeholder models and sample data, so the planner and the critic
have nothing to say. To see the steps work, give it a real model (and `--live` for public data):

    python -m bionexus.evals.ablation --disease "Crohn's disease" --genes NOD2,IL23R --live \
        --provider openai --model gpt-4o-mini --input-price 0.15 --output-price 0.60 \
        --price-date 2026-10-24

The key is read by name from your `.env`, as everywhere else. Prices must be ones you have checked.
"""

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date

from bionexus.config import Settings
from bionexus.container import build_container, initial_release
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.contracts.messages import MessageType
from bionexus.contracts.review import VerificationVerdict

USER = Principal(
    user_id="ablation",
    role=Role.SCIENTIST,
    tenant_id="ablation",
    project_ids=frozenset({"ablation"}),
    client_kind=ClientKind.SCIENTIST,
)

CONFIGS: dict[str, frozenset[str]] = {
    "all steps": frozenset(),
    "no coverage review": frozenset({"coverage"}),
    "no critic": frozenset({"critique"}),
    "no verifier": frozenset({"verify"}),
    "none of the three": frozenset({"coverage", "critique", "verify"}),
}


@dataclass(frozen=True)
class Row:
    config: str
    status: str
    evidence: int
    requests: int  # evidence.request messages sent
    explained: int  # conflicts the critic explained
    withheld: int  # claims and sentences the verifier withheld
    unchecked: int  # summary sentences kept but not checked
    model_calls: int
    cached: int
    cost_usd: float
    seconds: float


def run_config(
    label: str,
    disabled: frozenset[str],
    request: InvestigationRequest,
    settings: Settings,
    model: str,
) -> Row:
    app = build_container(
        {"a": USER},
        settings=settings,
        initial=initial_release(model, None) if model else None,
        disabled_steps=disabled,
    )
    started = time.perf_counter()
    run = app.investigations.submit(USER, "ablation", request, f"ablation-{label}")
    app.worker.run_pending()
    state = app.investigations.get(USER, run.run_id)
    verdicts = [v.verdict for v in state.verifications]
    return Row(
        config=label,
        status=state.status.value,
        evidence=len(state.evidence),
        requests=sum(m.type is MessageType.EVIDENCE_REQUEST for m in state.messages),
        explained=sum(1 for a in state.analyses.values() if a.explanation),
        withheld=verdicts.count(VerificationVerdict.UNSUPPORTED),
        unchecked=verdicts.count(VerificationVerdict.UNCHECKED),
        model_calls=len(state.invocations),
        cached=sum(i.cached for i in state.invocations),
        cost_usd=round(state.budget.spent_usd, 6),
        seconds=round(time.perf_counter() - started, 1),
    )


def run_all(request: InvestigationRequest, settings: Settings, model: str = "") -> list[Row]:
    return [run_config(label, off, request, settings, model) for label, off in CONFIGS.items()]


def render(rows: list[Row]) -> str:
    head = f"{'configuration':<20}{'status':<20}{'evidence':>9}{'requests':>9}{'explained':>10}"
    head += f"{'withheld':>9}{'unchecked':>10}{'calls':>6}{'cost $':>10}{'secs':>6}"
    lines = [head, "-" * len(head)]
    for r in rows:
        lines.append(
            f"{r.config:<20}{r.status:<20}{r.evidence:>9}{r.requests:>9}{r.explained:>10}"
            f"{r.withheld:>9}{r.unchecked:>10}{r.model_calls:>6}{r.cost_usd:>10.4f}{r.seconds:>6}"
        )
    return "\n".join(lines)


def _settings(args: argparse.Namespace) -> Settings:
    models = ""
    if args.model:
        spec = {
            "model_id": args.model,
            "provider": args.provider,
            "supports_structured_output": True,
            "api_key_secret": f"{args.provider.upper()}_API_KEY",
            "input_usd_per_million": args.input_price,
            "output_usd_per_million": args.output_price,
            "price_verified_on": args.price_date,
        }
        models = json.dumps({"models": [spec]})
    return Settings(
        run_budget_usd=args.budget,
        run_warn_usd=args.budget / 2,
        run_max_model_calls=40,
        live_sources=args.live,
        models_json=models,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--disease", default="Crohn's disease")
    parser.add_argument("--genes", default="NOD2,IL23R")
    parser.add_argument("--cutoff", default="2026-01-01")
    parser.add_argument("--live", action="store_true", help="query the public databases")
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    parser.add_argument("--model", default="", help="a real model id; omit for placeholder models")
    parser.add_argument("--input-price", type=float, default=0.0)
    parser.add_argument("--output-price", type=float, default=0.0)
    parser.add_argument("--price-date", default="")
    parser.add_argument("--budget", type=float, default=0.5, help="USD cap per run")
    args = parser.parse_args()
    request = InvestigationRequest(
        disease=args.disease,
        targets=tuple(args.genes.split(",")),
        question=f"What does public evidence say about {args.genes} in {args.disease}?",
        evidence_cutoff=date.fromisoformat(args.cutoff),
    )
    print("Behaviour of each step, not accuracy. Prices and model are yours; nothing is guessed.\n")
    print(render(run_all(request, _settings(args), args.model)))


if __name__ == "__main__":
    main()
