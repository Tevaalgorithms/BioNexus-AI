"""Live adapters. Each is a named BioNexus adapter (not an official MCP) returning EvidenceRecords.

Direction is never inferred by guesswork: where a source gives no direction the record is
`unknown`, and only an explicit literature extraction step may change that.

This module holds what every adapter shares: text helpers and the `LiveSource` base.
"""

import re
from datetime import date

from bionexus.sources.http import GuardedHttp

MAX_PASSAGE_CHARS = 1500
HUMAN = "human"
TAG = re.compile(r"<[^>]+>")


def plain(text: str | None) -> str:
    return TAG.sub("", text or "").strip()[:MAX_PASSAGE_CHARS]


STOP_WORDS = frozenset({"disease", "syndrome", "disorder", "the", "of"})


def normalise(text: str) -> str:
    """Lower-case and drop possessives so "Crohn's disease" matches "Crohn disease"."""
    return re.sub(r"['’]s\b", "", text.lower())


def disease_words(disease: str) -> list[str]:
    """Every meaningful word of the disease name must appear in a trait (not just the first)."""
    words = [w for w in normalise(disease).split() if w not in STOP_WORDS]
    return words or normalise(disease).split()


def parse_date(value: str | None, fallback: date | None = None) -> date:
    """Accepts YYYY, YYYY-MM or YYYY-MM-DD; partial dates resolve to their first day."""
    parts = (value or "").split("-")
    try:
        numbers = [int(p) for p in parts[:3]] + [1] * (3 - len(parts))
        return date(*numbers[:3])
    except ValueError:
        return fallback or date.today()


class LiveSource:
    name: str

    def __init__(self, http: GuardedHttp) -> None:
        self._http = http

    def snapshot_id(self) -> str:
        return "live-api"

    def passage_for(self, source_id: str) -> str | None:
        return None
