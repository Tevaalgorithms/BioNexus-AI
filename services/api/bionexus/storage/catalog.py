"""Persistence port for the model catalogue, plus the in-memory adapter."""

from typing import Protocol


class ModelCatalog(Protocol):
    def get(self, model_id: str) -> dict | None: ...
    def put(self, row: dict) -> None: ...
    def list(self) -> list[dict]: ...


class InMemoryCatalog:
    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    def get(self, model_id: str) -> dict | None:
        return self._rows.get(model_id)

    def put(self, row: dict) -> None:
        self._rows[row["model_id"]] = dict(row)

    def list(self) -> list[dict]:
        return [dict(r) for r in self._rows.values()]
