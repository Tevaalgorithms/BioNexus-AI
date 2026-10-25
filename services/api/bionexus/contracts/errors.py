"""Domain errors. Each carries a stable `code`; the API layer maps codes to HTTP statuses."""


class BioNexusError(Exception):
    code = "internal_error"


class AccessDenied(BioNexusError):
    code = "access_denied"


class NotFound(BioNexusError):
    code = "not_found"


class Conflict(BioNexusError):
    code = "conflict"


class InvalidRequest(BioNexusError):
    code = "invalid_request"


class RateLimited(BioNexusError):
    code = "rate_limited"


class ProvisioningFailed(BioNexusError):
    """The identity provider could not create or change an account."""

    code = "provisioning_failed"


class InvalidTransition(BioNexusError):
    code = "invalid_transition"


class RouteRejected(BioNexusError):
    code = "route_rejected"


class RecoverableRunError(BioNexusError):
    """The run cannot finish, but ended honestly: it is reported as `incomplete`."""

    code = "run_incomplete"


class BudgetExceeded(RecoverableRunError):
    code = "budget_exceeded"


class SourceUnavailable(RecoverableRunError):
    code = "source_unavailable"


class ModelUnavailable(RecoverableRunError):
    code = "model_unavailable"


class NoEvidenceFound(RecoverableRunError):
    code = "no_evidence"


class RunCancelled(BioNexusError):
    code = "run_cancelled"
