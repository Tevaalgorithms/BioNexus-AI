"""The six live source adapters, one module each. Import them from here."""

from bionexus.sources.http import GuardedHttp
from bionexus.sources.live.clinical_trials import ClinicalTrialsSource
from bionexus.sources.live.common import LiveSource, disease_words, normalise, parse_date, plain
from bionexus.sources.live.europe_pmc import EuropePmcSource
from bionexus.sources.live.gwas import GwasCatalogSource
from bionexus.sources.live.monarch import MonarchSource
from bionexus.sources.live.open_targets import OpenTargetsSource
from bionexus.sources.live.reactome import ReactomeSource

__all__ = [
    "ClinicalTrialsSource",
    "EuropePmcSource",
    "GwasCatalogSource",
    "LiveSource",
    "MonarchSource",
    "OpenTargetsSource",
    "ReactomeSource",
    "disease_words",
    "live_sources",
    "normalise",
    "parse_date",
    "plain",
]


def live_sources(http: GuardedHttp) -> list[LiveSource]:
    return [
        OpenTargetsSource(http),
        GwasCatalogSource(http),
        EuropePmcSource(http),
        ReactomeSource(http),
        MonarchSource(http),
        ClinicalTrialsSource(http),
    ]
