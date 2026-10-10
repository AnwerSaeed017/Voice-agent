from abc import ABC, abstractmethod


class ISeedService(ABC):
    @abstractmethod
    def seed_if_empty(self) -> int:
        """Insert demo patients when the table is empty. Returns how many were added."""
