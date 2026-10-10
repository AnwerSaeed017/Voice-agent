from abc import ABC, abstractmethod


class ISqlLoader(ABC):
    @abstractmethod
    def load(self, name: str) -> str:
        """Return the contents of app/sql/<name>.sql."""
