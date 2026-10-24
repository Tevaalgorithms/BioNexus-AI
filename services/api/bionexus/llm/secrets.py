"""Secret lookup by *name*. Values come from the parameter source (SSM in production)."""

from bionexus.params import parameters


def resolve_secret(name: str) -> str:
    return parameters().require(name)


def secret_is_configured(name: str) -> bool:
    return parameters().has(name)
