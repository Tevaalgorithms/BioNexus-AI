"""Where configuration comes from.

* Production (`APP_ENV=production`): AWS SSM Parameter Store, under `SSM_PATH_PREFIX`.
  Values are read with decryption (SecureString) and refreshed every `ttl` seconds, so changes such
  as budgets apply without a restart. Environment variables are NOT consulted for settings.
* Anywhere else (local development): a `.env` file; real environment variables override it.

Only three bootstrap variables are read from the process environment: APP_ENV, SSM_PATH_PREFIX and
AWS_REGION (plus the AWS credential chain used by boto3) and the optional
BIONEXUS_PARAM_REFRESH_SECONDS (default 300).
"""

import contextlib
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from bionexus.contracts.errors import InvalidRequest

DEFAULT_PREFIX = "/bionexus/prod/"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
# Each refresh decrypts SecureStrings through KMS (billed per request after 20,000 free a month).
# Five minutes keeps that near zero; lower it only if you need faster rotation.
REFRESH_SECONDS = float(os.environ.get("BIONEXUS_PARAM_REFRESH_SECONDS", "300"))


class ParameterSource(Protocol):
    def load(self) -> dict[str, str]: ...


def parse_dotenv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


class DotEnvSource:
    """Local development: `.env` file, overridden by real environment variables."""

    def __init__(
        self, path: Path = DEFAULT_ENV_FILE, environ: dict[str, str] | None = None
    ) -> None:
        self._path = path
        self._environ = os.environ if environ is None else environ

    def load(self) -> dict[str, str]:
        values = parse_dotenv(self._path.read_text()) if self._path.is_file() else {}
        return {**values, **{k: v for k, v in self._environ.items() if k in values}}


class SsmSource:
    """Production: every parameter below the prefix, decrypted, keyed by its relative name."""

    def __init__(self, prefix: str, region: str | None = None, client=None) -> None:
        self._prefix = prefix if prefix.endswith("/") else prefix + "/"
        if client is None:
            import boto3  # imported lazily: local development does not need AWS

            client = boto3.client("ssm", region_name=region)
        self._client = client

    def load(self) -> dict[str, str]:
        values: dict[str, str] = {}
        pages = self._client.get_paginator("get_parameters_by_path").paginate(
            Path=self._prefix, Recursive=True, WithDecryption=True
        )
        for page in pages:
            for item in page["Parameters"]:
                values[item["Name"][len(self._prefix) :].replace("/", "_")] = item["Value"]
        return values


class Parameters:
    """Cached view of a source. A failed refresh keeps the last known-good values."""

    def __init__(
        self,
        source: ParameterSource,
        ttl: float = REFRESH_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source, self._ttl, self._clock = source, ttl, clock
        self._values: dict[str, str] = source.load()
        self._loaded_at = clock()

    def _fresh(self) -> dict[str, str]:
        if self._clock() - self._loaded_at >= self._ttl:
            with contextlib.suppress(Exception):  # keep serving the last known-good values
                self._values = self._source.load()
            self._loaded_at = self._clock()
        return self._values

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._fresh().get(name, default)

    def has(self, name: str) -> bool:
        return bool(self._fresh().get(name))

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise InvalidRequest(f"Required parameter '{name}' is not configured")
        return value

    def is_production(self) -> bool:
        return os.environ.get("APP_ENV") == "production"


def build_parameters() -> Parameters:
    if os.environ.get("APP_ENV") == "production":
        prefix = os.environ.get("SSM_PATH_PREFIX", DEFAULT_PREFIX)
        return Parameters(SsmSource(prefix, os.environ.get("AWS_REGION")))
    return Parameters(DotEnvSource(Path(os.environ.get("BIONEXUS_ENV_FILE") or DEFAULT_ENV_FILE)))


_current: Parameters | None = None


def parameters() -> Parameters:
    global _current
    if _current is None:
        _current = build_parameters()
    return _current


def set_parameters(params: Parameters | None) -> None:
    """Tests and entry points install a specific source (or None to rebuild lazily)."""
    global _current
    _current = params
