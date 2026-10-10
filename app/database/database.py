"""Database connection: owns the engine and hands out transactional sessions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.interfaces.utilities import IDatabase


class Database(IDatabase):
    def __init__(self, url: str) -> None:
        is_sqlite = url.startswith("sqlite")
        self._engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if is_sqlite else {},
        )
        if is_sqlite:
            event.listen(self._engine, "connect", self._enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """One unit of work: commit on success, roll back on any error."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute_scalar(self, sql: str) -> object:
        with self._engine.connect() as connection:
            return connection.execute(text(sql)).scalar()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
