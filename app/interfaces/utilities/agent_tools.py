from abc import ABC, abstractmethod


class IAgentTools(ABC):
    @abstractmethod
    def definitions(self) -> list[dict]:
        """Tool definitions in Vapi's format."""
