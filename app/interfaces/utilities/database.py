from abc import ABC, abstractmethod
from collections.abc import Mapping
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session


class IDatabase(ABC):
    @abstractmethod
    def call(self, function: str, **arguments: object) -> list[Mapping]:
        """Call a SQL function (app/sql/functions) with named arguments; returns its rows."""

    @abstractmethod
    def call_value(self, function: str, **arguments: object) -> object:
        """Call a SQL function that returns a single value."""

    @abstractmethod
    def session(self) -> AbstractContextManager[Session]:
        """A transactional ORM session, for tooling outside the repositories."""

    @abstractmethod
    def execute_scalar(self, sql: str) -> object:
        """Run a SQL statement loaded from app/sql and return its single value."""
