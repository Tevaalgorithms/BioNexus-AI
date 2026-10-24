"""How a record's direction was decided, so the critic and the literature agent agree on it."""

from bionexus.contracts.evidence import EvidenceRecord

MODEL_STANCE_NOTE = "stance extracted by model (unreviewed)"
RECHECKED_NOTE = "direction re-checked on the full passage (unreviewed)"


def is_model_read(record: EvidenceRecord) -> bool:
    """True while the direction came from a model reading an excerpt and has not been re-checked."""
    return MODEL_STANCE_NOTE in record.context
