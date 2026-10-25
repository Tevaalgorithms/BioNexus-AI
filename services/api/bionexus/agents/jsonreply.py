"""Reading structured answers from a model. Model text is untrusted, so a bad reply is just None."""

import json


def parse_json_object(text: str) -> dict | None:
    """The first JSON object in `text`, or None. Never raises."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
