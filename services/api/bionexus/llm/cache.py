"""AO-5: an identical prompt is paid for once. A small, per-process answer cache for the gateway.

What it is: when the same organisation sends the same prompt to the same model setup again (for
example re-analysing a gene, where every paper is classified again), the stored answer is returned
and no model is called. What it is not: the provider's own prompt caching, which a provider applies
by itself to long prompts that begin with the same text.

Safety: the key includes the organisation, so one organisation never receives another's answer,
and the model chain, output cap and temperature, so changing a setting never reuses an old answer.
Only a hash of the prompt is kept, never the prompt. The cache lives in memory, is bounded, and is
emptied on restart.
"""

import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass

from bionexus.llm.models import AgentBinding


@dataclass(frozen=True)
class CachedAnswer:
    text: str
    model_id: str  # the model that originally answered


class ResponseCache:
    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._items: OrderedDict[str, CachedAnswer] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key(tenant_id: str, binding: AgentBinding, prompt: str) -> str:
        parts = [tenant_id, binding.model_chain(), binding.max_output_tokens, binding.temperature]
        material = json.dumps([*parts, prompt], default=str)
        return hashlib.sha256(material.encode()).hexdigest()

    def get(self, key: str) -> CachedAnswer | None:
        with self._lock:
            answer = self._items.get(key)
            if answer is not None:
                self._items.move_to_end(key)  # recently used stays longest
            return answer

    def put(self, key: str, answer: CachedAnswer) -> None:
        if self._max_entries <= 0:
            return
        with self._lock:
            self._items[key] = answer
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)  # drop the least recently used
