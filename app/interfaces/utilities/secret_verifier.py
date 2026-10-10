from abc import ABC, abstractmethod


class ISecretVerifier(ABC):
    @abstractmethod
    def is_valid(self, provided: str | None) -> bool: ...
