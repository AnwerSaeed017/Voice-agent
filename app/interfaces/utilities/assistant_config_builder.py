from abc import ABC, abstractmethod


class IAssistantConfigBuilder(ABC):
    @abstractmethod
    def build(self) -> dict:
        """The full Vapi assistant payload."""
