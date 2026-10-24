"""Assembles every PostgreSQL adapter into the `Storage` the application uses."""

from bionexus.storage.ports import Storage
from bionexus.storage.postgres.audit import PostgresAudit
from bionexus.storage.postgres.catalog import PostgresCatalog
from bionexus.storage.postgres.database import Database
from bionexus.storage.postgres.events import PostgresEvents
from bionexus.storage.postgres.flags import PostgresFlags
from bionexus.storage.postgres.jobs import PostgresJobs
from bionexus.storage.postgres.memory import PostgresMemory
from bionexus.storage.postgres.projects import PostgresProjects
from bionexus.storage.postgres.releases import PostgresReleases
from bionexus.storage.postgres.reports import PostgresReports
from bionexus.storage.postgres.runs import PostgresRuns
from bionexus.storage.postgres.users import PostgresUsers


def postgres_storage(db: Database, embedding_dim: int = 64) -> Storage:
    from bionexus.retrieval.postgres import PostgresRetrieval  # lazy: retrieval imports Database

    return Storage(
        runs=PostgresRuns(db),
        jobs=PostgresJobs(db),
        reports=PostgresReports(db),
        audit=PostgresAudit(db),
        memory=PostgresMemory(db),
        releases=PostgresReleases(db),
        users=PostgresUsers(db),
        events=PostgresEvents(db),
        flags=PostgresFlags(db),
        catalog=PostgresCatalog(db),
        checkpointer=db.checkpoint_saver(),
        projects=PostgresProjects(db),
        retrieval=PostgresRetrieval(db, embedding_dim),
    )
