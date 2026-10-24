"""Connection handling shared by every PostgreSQL adapter."""

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.abc import Query
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


class Database:
    """Thin wrapper so adapters stay free of connection handling."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._checkpoint_pool: ConnectionPool | None = None
        self._pool = ConnectionPool(
            dsn, min_size=1, max_size=5, open=True, kwargs={"row_factory": dict_row}
        )

    def fetch_all(self, sql: Query, params: tuple | dict = ()) -> list[dict]:
        with self._pool.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: Query, params: tuple | dict = ()) -> dict | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: Query, params: tuple | dict = ()) -> None:
        with self._pool.connection() as conn:
            conn.execute(sql, params)

    def checkpoint_saver(self) -> PostgresSaver:
        """LangGraph's durable checkpoints. It needs its own autocommit connections."""
        self._checkpoint_pool = ConnectionPool(
            self._dsn,
            min_size=1,
            max_size=5,
            open=True,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        saver = PostgresSaver(self._checkpoint_pool)
        saver.setup()  # creates/updates LangGraph's own tables
        return saver

    def close(self) -> None:
        self._pool.close()
        if self._checkpoint_pool is not None:
            self._checkpoint_pool.close()


def to_jsonb(model) -> Jsonb:
    """A pydantic model as a JSONB parameter."""
    return Jsonb(model.model_dump(mode="json"))
