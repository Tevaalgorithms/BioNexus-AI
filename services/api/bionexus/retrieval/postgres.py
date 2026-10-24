"""PostgreSQL retrieval: full-text search + pgvector, with tenant/cutoff filters in SQL (RAG-03).

The one dynamic part of any statement is the chunk-table name (it carries the embedding
dimension, so a new model size is a new index). It is composed with `psycopg.sql.Identifier`,
never by string formatting, and every value is a bound parameter.
"""

from psycopg import sql

from bionexus.contracts.evidence import EvidenceRecord
from bionexus.retrieval.models import Edge, Scope
from bionexus.storage.postgres import Database

SCOPE_FILTER = (
    "tenant_id = %(tenant)s AND project_id = %(project)s AND run_id = %(run)s "
    "AND license_ok AND review_state <> 'excluded' AND available_on <= %(cutoff)s"
)


def _params(scope: Scope, **extra) -> dict:
    base = {
        "tenant": scope.tenant_id,
        "project": scope.project_id,
        "run": scope.run_id,
        "cutoff": scope.cutoff,
    }
    return {**base, **extra}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


CREATE_CHUNKS = """CREATE TABLE IF NOT EXISTS {table} (
    tenant_id text NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
    evidence_id text NOT NULL, body text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
    embedding vector({dim}) NOT NULL, embedding_model text NOT NULL,
    license_ok boolean NOT NULL, review_state text NOT NULL, available_on date NOT NULL,
    PRIMARY KEY (tenant_id, project_id, run_id, evidence_id, embedding_model))"""

CREATE_EDGES = """CREATE TABLE IF NOT EXISTS evidence_edges (
    tenant_id text NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
    subject text NOT NULL, relation text NOT NULL, object text NOT NULL,
    evidence_id text NOT NULL, species text NOT NULL, direction text NOT NULL,
    PRIMARY KEY (tenant_id, project_id, run_id, subject, relation, object, evidence_id))"""

INSERT_CHUNK = """INSERT INTO {table}
    (tenant_id, project_id, run_id, evidence_id, body, embedding, embedding_model,
     license_ok, review_state, available_on)
    VALUES (%s,%s,%s,%s,%s,%s::vector,%s,%s,%s,%s)
    ON CONFLICT DO NOTHING"""

LEXICAL = (
    "SELECT evidence_id FROM {table} WHERE " + SCOPE_FILTER + " "  # nosec B608 (constants only)
    "AND tsv @@ plainto_tsquery('english', %(q)s) "
    "ORDER BY ts_rank(tsv, plainto_tsquery('english', %(q)s)) DESC, evidence_id LIMIT %(limit)s"
)

VECTOR = (
    "SELECT evidence_id FROM {table} WHERE " + SCOPE_FILTER + " "  # nosec B608 (constants only)
    "AND embedding_model = %(model)s "
    "ORDER BY embedding <=> %(v)s::vector, evidence_id LIMIT %(limit)s"
)

EDGES_FROM = """SELECT e.subject, e.relation, e.object, e.evidence_id, e.species, e.direction
    FROM evidence_edges e
    JOIN {table} c ON (c.tenant_id, c.project_id, c.run_id, c.evidence_id)
         = (e.tenant_id, e.project_id, e.run_id, e.evidence_id)
    WHERE e.tenant_id = %(tenant)s AND e.project_id = %(project)s
      AND e.run_id = %(run)s AND e.subject = ANY(%(nodes)s)
      AND e.relation = ANY(%(relations)s)
      AND c.license_ok AND c.review_state <> 'excluded'
      AND c.available_on <= %(cutoff)s"""


class PostgresRetrieval:
    def __init__(self, db: Database, dim: int) -> None:
        self._db = db
        self._dim = int(dim)
        self._table = sql.Identifier(
            f"evidence_chunks_{self._dim}"
        )  # a new dimension is a new index
        self._create_tables()

    def _statement(self, template: str) -> sql.Composed:
        return sql.SQL(template).format(table=self._table, dim=sql.Literal(self._dim))

    def _create_tables(self) -> None:
        index = sql.Identifier(f"evidence_chunks_{self._dim}_tsv")
        self._db.execute(self._statement(CREATE_CHUNKS))
        self._db.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} USING gin (tsv)").format(
                index=index, table=self._table
            )
        )
        self._db.execute(sql.SQL(CREATE_EDGES))

    def add_chunks(self, scope, records: list[EvidenceRecord], vectors, model: str) -> None:
        statement = self._statement(INSERT_CHUNK)
        for record, vector in zip(records, vectors, strict=True):
            self._db.execute(
                statement,
                (
                    scope.tenant_id,
                    scope.project_id,
                    scope.run_id,
                    record.evidence_id,
                    f"{record.finding} {record.passage} {record.target}",
                    _vector_literal(vector),
                    model,
                    record.license_ok,
                    record.review_state.value,
                    record.available_on,
                ),
            )

    def lexical(self, scope: Scope, query: str, limit: int) -> list[str]:
        rows = self._db.fetch_all(
            self._statement(LEXICAL),
            _params(scope, q=query, limit=limit),  # type: ignore[arg-type]
        )
        return [r["evidence_id"] for r in rows]

    def vector(self, scope: Scope, vector: list[float], model: str, limit: int) -> list[str]:
        rows = self._db.fetch_all(
            self._statement(VECTOR),
            _params(scope, model=model, v=_vector_literal(vector), limit=limit),  # type: ignore[arg-type]
        )
        return [r["evidence_id"] for r in rows]

    def add_edges(self, scope: Scope, edges: list[Edge]) -> None:
        for edge in edges:
            self._db.execute(
                "INSERT INTO evidence_edges VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (
                    scope.tenant_id,
                    scope.project_id,
                    scope.run_id,
                    edge.subject,
                    edge.relation,
                    edge.object,
                    edge.evidence_id,
                    edge.species,
                    edge.direction,
                ),
            )

    def edges_from(self, scope: Scope, nodes: list[str], relations: frozenset[str]) -> list[Edge]:
        rows = self._db.fetch_all(
            self._statement(EDGES_FROM),
            _params(scope, nodes=nodes, relations=list(relations)),  # type: ignore[arg-type]
        )
        return [Edge(**r) for r in rows]
