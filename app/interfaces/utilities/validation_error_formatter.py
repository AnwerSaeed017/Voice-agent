from abc import ABC, abstractmethod
from collections.abc import Sequence


class IValidationErrorFormatter(ABC):
    @abstractmethod
    def format(self, errors: Sequence[dict]) -> list[dict]:
        """Turn Pydantic error dicts into [{"field": ..., "message": ...}]."""
