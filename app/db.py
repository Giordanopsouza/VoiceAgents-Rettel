from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine

from app.models import Base


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    autocommit = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()
        dbapi_connection.autocommit = autocommit
    # sqlite3 would otherwise emit a deferred BEGIN. SQLAlchemy emits
    # BEGIN IMMEDIATE so overlapping writers serialize before they read
    # slot state, including Retell retries on the booking path.
    dbapi_connection.isolation_level = None


def _begin_immediate(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def init_db(database_path: Path) -> Engine:
    """Create the SQLite file if needed and apply the calendar schema."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{database_path.resolve()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
    event.listen(engine, "begin", _begin_immediate)
    Base.metadata.create_all(engine)
    return engine
