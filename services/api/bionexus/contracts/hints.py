"""A search hint: one extra term a specialist may add to its own search, validated before use.

A hint is data from a model, so it is never trusted. It is a short plain phrase (letters, digits and
a little punctuation), never a query operator, and it only widens a search on a source that
supports it. Anything else is dropped.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

MAX_HINT_CHARS = 60
_ALLOWED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.'’()/+\-]*$")


class HintKind(StrEnum):
    DISEASE = "disease"  # another name for the disease
    GENE = "gene"  # another name (alias) for a gene
    CONTEXT = "context"  # a qualifier, such as an ancestry or an assay


class SearchHint(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: HintKind
    text: str


def clean_hint(kind: object, text: object) -> SearchHint | None:
    """A valid hint, or None. Never raises: model output is untrusted."""
    if not isinstance(kind, str) or not isinstance(text, str):
        return None
    if kind not in HintKind._value2member_map_:
        return None
    phrase = " ".join(text.split())
    if len(phrase) < 2 or len(phrase) > MAX_HINT_CHARS or not _ALLOWED.match(phrase):
        return None
    return SearchHint(kind=HintKind(kind), text=phrase)
