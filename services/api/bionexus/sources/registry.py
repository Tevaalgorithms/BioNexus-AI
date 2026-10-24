"""Allowlisted sources, looked up by name. Agents cannot reach anything not registered here."""

import time

from bionexus.contracts.errors import SourceUnavailable
from bionexus.sources.base import EvidenceSource
from bionexus.sources.fixture import FixtureSource

SOURCE_NAMES = ("open_targets", "gwas", "europe_pmc", "reactome", "monarch", "clinicaltrials")

# What each source is, for the admin console. Every one is a BioNexus adapter that calls the
# provider's public web API over HTTPS; none is an MCP server (an official MCP server could later be
# wrapped behind the same adapter interface).
SOURCE_META: dict[str, dict[str, str]] = {
    "open_targets": {
        "label": "Open Targets",
        "agent": "genetics",
        "protocol": "GraphQL",
        "host": "api.platform.opentargets.org",
        "provides": "Gene–disease association scores from many evidence types",
    },
    "gwas": {
        "label": "GWAS Catalog",
        "agent": "genetics",
        "protocol": "REST",
        "host": "www.ebi.ac.uk (gwas/rest/api/v2)",
        "provides": "Published genome-wide association results",
    },
    "europe_pmc": {
        "label": "Europe PMC",
        "agent": "literature",
        "protocol": "REST",
        "host": "www.ebi.ac.uk (europepmc)",
        "provides": "Papers, abstracts and open-access status",
    },
    "reactome": {
        "label": "Reactome",
        "agent": "pathways",
        "protocol": "REST",
        "host": "reactome.org",
        "provides": "Curated biological pathways",
    },
    "monarch": {
        "label": "Monarch Initiative",
        "agent": "pathways",
        "protocol": "REST",
        "host": "api-v3.monarchinitiative.org",
        "provides": "Gene–phenotype associations",
    },
    "clinicaltrials": {
        "label": "ClinicalTrials.gov",
        "agent": "clinical",
        "protocol": "REST",
        "host": "clinicaltrials.gov",
        "provides": "Registered clinical studies and their status",
    },
}


class SourceRegistry:
    def __init__(self, sources: list[EvidenceSource]) -> None:
        self._sources = {source.name: source for source in sources}

    @classmethod
    def from_fixtures(cls) -> "SourceRegistry":
        return cls([FixtureSource(name) for name in SOURCE_NAMES])

    def get(self, name: str) -> EvidenceSource:
        source = self._sources.get(name)
        if source is None:
            raise SourceUnavailable(f"Source '{name}' is not registered")
        return source

    def snapshots(self) -> dict[str, str]:
        return {name: source.snapshot_id() for name, source in self._sources.items()}

    def fixture_diseases(self) -> list[str]:
        """Diseases the offline demo data can answer; empty when live sources are in use."""
        names = {s.disease_name() for s in self._sources.values() if hasattr(s, "disease_name")}
        return sorted(names)

    def describe(self) -> list[dict[str, str]]:
        """Source list with access mode and snapshot (SOURCE-01/12)."""
        return [
            {
                "name": name,
                "mode": "live" if source.snapshot_id() == "live-api" else "fixture",
                "snapshot": source.snapshot_id(),
                **SOURCE_META.get(name, {}),
            }
            for name, source in self._sources.items()
        ]

    def check(self, name: str) -> dict[str, object]:
        """Real request against one source, reported as data (never raises to the caller)."""
        started = time.monotonic()
        try:
            count = len(self.get(name).search("Crohn disease", ("NOD2",)))
        except SourceUnavailable as error:
            return {"name": name, "ok": False, "detail": str(error)}
        latency = round((time.monotonic() - started) * 1000)
        return {"name": name, "ok": True, "records": count, "latency_ms": latency}
