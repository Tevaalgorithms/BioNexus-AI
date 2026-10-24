"""Forward-only SQL migrations. `python -m bionexus.storage.migrate` applies pending files."""

from pathlib import Path

from bionexus.params import parameters
from bionexus.storage.postgres import Database

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def pending_migrations(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]


def migrate(db: Database) -> list[str]:
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
    applied = {r["name"] for r in db.fetch_all("SELECT name FROM schema_migrations")}
    done = []
    for path in pending_migrations(applied):
        db.execute(path.read_text())
        db.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        done.append(path.name)
    return done


if __name__ == "__main__":
    database = Database(parameters().require("BIONEXUS_DATABASE_URL"))
    print("applied:", migrate(database) or "nothing to do")
    database.close()
