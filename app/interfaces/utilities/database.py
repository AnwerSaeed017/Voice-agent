from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session


class IDatabase(ABC):
    @abstractmethod
    def session(self) -> AbstractContextManager[Session]:
        """A transactional session: commits on success, rolls back on error."""

    @abstractmethod
    def execute_scalar(self, sql: str) -> object:
        """Run a raw SQL statement and return its single value."""
