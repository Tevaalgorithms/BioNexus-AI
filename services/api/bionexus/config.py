"""Runtime settings with safe pilot defaults, read from SSM (production) or `.env` (local)."""

from dataclasses import dataclass

from bionexus.params import parameters


@dataclass(frozen=True)
class Settings:
    run_budget_usd: float = 10.0
    run_warn_usd: float = 5.0
    run_max_model_calls: int = 40
    tenant_monthly_budget_usd: float = 200.0
    models_file: str = ""
    models_json: str = ""
    inline_worker: bool = True
    live_sources: bool = False

    @classmethod
    def current(cls) -> "Settings":
        """Re-read on every call, so SSM changes take effect within the refresh interval."""
        p = parameters()
        d = cls()
        return cls(
            run_budget_usd=float(p.get("BIONEXUS_RUN_BUDGET_USD", d.run_budget_usd)),
            run_warn_usd=float(p.get("BIONEXUS_RUN_WARN_USD", d.run_warn_usd)),
            run_max_model_calls=int(p.get("BIONEXUS_RUN_MAX_CALLS", d.run_max_model_calls)),
            tenant_monthly_budget_usd=float(
                p.get("BIONEXUS_TENANT_MONTHLY_USD", d.tenant_monthly_budget_usd)
            ),
            models_file=p.get("BIONEXUS_MODELS_FILE", d.models_file) or "",
            models_json=p.get("BIONEXUS_MODELS_JSON", d.models_json) or "",
            inline_worker=p.get("BIONEXUS_INLINE_WORKER", "1") == "1",
            live_sources=p.get("BIONEXUS_SOURCES", "fixture") == "live",
        )
