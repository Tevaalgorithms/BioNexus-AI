"""PostgreSQL adapters implementing the storage ports: one module per store.

Payloads are JSONB; hot columns are real. Import `Database` and `postgres_storage` from here.
"""

from bionexus.storage.postgres.database import Database
from bionexus.storage.postgres.factory import postgres_storage

__all__ = ["Database", "postgres_storage"]
