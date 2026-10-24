"""Guarded outbound HTTP for live sources: host allowlist, timeouts, bounded retries, size cap."""

import random
import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from bionexus.contracts.errors import SourceUnavailable

ALLOWED_HOSTS = frozenset(
    {
        "www.ebi.ac.uk",
        "api.platform.opentargets.org",
        "reactome.org",
        "api-v3.monarchinitiative.org",
        "clinicaltrials.gov",
    }
)
TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2
MAX_RESPONSE_BYTES = 2_000_000
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class GuardedHttp:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS)
        self._sleep = sleep

    def get_json(self, url: str, params: dict | None = None) -> dict:
        return self._request("GET", url, params=params)

    def post_json(self, url: str, body: dict) -> dict:
        return self._request("POST", url, json=body)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        self._check_host(url)
        last_error = "no attempt made"
        for attempt in range(MAX_RETRIES + 1):
            outcome = self._attempt(method, url, kwargs)
            if isinstance(outcome, dict):
                return outcome
            last_error = outcome
            self._sleep(random.uniform(0, 0.25 * (2**attempt)))  # nosec B311 (retry jitter)
        raise SourceUnavailable(f"{urlparse(url).hostname}: {last_error}")

    def _attempt(self, method: str, url: str, kwargs: dict) -> dict | str:
        """Returns parsed JSON on success, or a short error string when a retry is allowed."""
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TransportError as error:
            return type(error).__name__
        if response.status_code in RETRYABLE_STATUS:
            return f"HTTP {response.status_code}"
        if response.status_code >= 400:
            raise SourceUnavailable(f"{urlparse(url).hostname}: HTTP {response.status_code}")
        return self._parse(response, url)

    @staticmethod
    def _parse(response: httpx.Response, url: str) -> dict:
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise SourceUnavailable(f"{urlparse(url).hostname}: response too large")
        try:
            return response.json()
        except ValueError as error:
            raise SourceUnavailable(f"{urlparse(url).hostname}: invalid JSON") from error

    @staticmethod
    def _check_host(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise SourceUnavailable(f"Outbound destination not allowed: {parsed.hostname}")
