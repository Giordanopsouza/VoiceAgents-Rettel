from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.models import Base


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    autocommit = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
        dbapi_connection.autocommit = autocommit


def init_db(database_path: Path) -> Engine:
    """Create the SQLite file if needed and apply the calendar schema."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{database_path.resolve()}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
    Base.metadata.create_all(engine)
    return engine
