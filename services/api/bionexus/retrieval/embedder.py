"""Embedding models are versioned: a new model or dimension means a new index (MODEL-15)."""

import hashlib
import math
import re
from typing import Protocol

from bionexus.llm.secrets import resolve_secret

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic, offline, free. Lexical-ish vectors for tests and demos; not semantic."""

    model_id = "hashing-v1"

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in TOKEN.findall(text.lower()):
            bucket = (
                int(hashlib.md5(token.encode(), usedforsecurity=False).hexdigest(), 16) % self.dim
            )
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class OpenAIEmbedder:
    """Hosted embeddings through LangChain's `OpenAIEmbeddings`. Batches are bounded (RAG-02)."""

    BATCH = 64

    def __init__(
        self,
        model_id: str,
        dim: int,
        secret_name: str = "OPENAI_API_KEY",  # nosec B107 (a name)
    ) -> None:
        self.model_id, self.dim, self._secret = model_id, dim, secret_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        from langchain_openai import OpenAIEmbeddings  # imported lazily: offline use needs no key

        client = OpenAIEmbeddings(
            model=self.model_id,
            dimensions=self.dim,
            api_key=resolve_secret(self._secret),
            chunk_size=self.BATCH,
        )
        return client.embed_documents(texts)
