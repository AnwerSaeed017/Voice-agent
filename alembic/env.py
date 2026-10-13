"""Alembic entry point. Run with: alembic upgrade head"""

from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import Settings
from app.database.base import Base


class MigrationEnvironment:
    """Runs migrations against the same DATABASE_URL the application uses."""

    def __init__(self) -> None:
        self._url = Settings().database_url
        if not self._url.startswith("postgresql"):
            raise RuntimeError("DATABASE_URL must be set to a PostgreSQL URL before running migrations.")
        self._target_metadata = Base.metadata

    def run(self) -> None:
        if context.is_offline_mode():
            self._run_offline()
        else:
            self._run_online()

    def _run_offline(self) -> None:
        context.configure(
            url=self._url,
            target_metadata=self._target_metadata,
            literal_binds=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    def _run_online(self) -> None:
        engine = create_engine(self._url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=self._target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


MigrationEnvironment().run()
