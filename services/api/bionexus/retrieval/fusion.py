"""Deterministic reciprocal-rank fusion of lexical and vector rankings (RAG-04)."""

RRF_K = 60


def fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    """Each ranking is best-first. Ties break on id so results are reproducible."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (RRF_K + position)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
