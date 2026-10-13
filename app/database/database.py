"""Database connection: owns the engine, calls SQL functions, hands out sessions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from app.constants.constants import SQL_IDENTIFIER
from app.interfaces.utilities import IDatabase


class Database(IDatabase):
    def __init__(self, url: str) -> None:
        if not url.startswith("postgresql"):
            raise RuntimeError(
                "DATABASE_URL must be set to a PostgreSQL URL. The data layer calls "
                "PostgreSQL functions (app/sql/functions), so no other database is supported."
            )
        self._engine = create_engine(url, pool_pre_ping=True)
        self._session_factory = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False
        )

    def call(self, function: str, **arguments: object) -> list[RowMapping]:
        """Call a SQL function by name in its own transaction and return its rows.

        This is the only place the call statement is written. Values are always bound,
        never interpolated; the function and argument names are checked identifiers.
        """
        for name in (function, *arguments):
            if not SQL_IDENTIFIER.match(name):
                raise ValueError(f"Not a valid SQL identifier: {name!r}")
        named = ", ".join(f"{name} => :{name}" for name in arguments)
        statement = text(f"SELECT * FROM {function}({named})")
        with self._engine.begin() as connection:
            return list(connection.execute(statement, arguments).mappings())

    def call_value(self, function: str, **arguments: object) -> object:
        rows = self.call(function, **arguments)
        return next(iter(rows[0].values())) if rows else None

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
