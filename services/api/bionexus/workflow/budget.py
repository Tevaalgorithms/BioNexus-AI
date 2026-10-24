"""Per-run spending cap. Reserve before a call, settle after, so a call can never overshoot."""

from pydantic import BaseModel

from bionexus.contracts.errors import BudgetExceeded


class Budget(BaseModel):
    max_cost_usd: float
    max_calls: int
    warn_usd: float = 5.0
    spent_usd: float = 0.0
    calls: int = 0

    def reserve(self, worst_case_usd: float) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded("Call limit reached")
        if self.spent_usd + worst_case_usd > self.max_cost_usd:
            raise BudgetExceeded("Cost limit reached")
        self.calls += 1
        self.spent_usd += worst_case_usd

    def settle(self, *, reserved: float, actual: float) -> None:
        self.spent_usd += actual - reserved

    @property
    def warning(self) -> bool:
        """True once spend passes the soft limit (SCOPE-08); the hard limit still stops the run."""
        return self.spent_usd >= self.warn_usd
