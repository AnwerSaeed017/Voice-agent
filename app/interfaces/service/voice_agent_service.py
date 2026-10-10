from abc import ABC, abstractmethod


class IVoiceAgentService(ABC):
    @abstractmethod
    def handle_message(self, message: dict) -> dict:
        """Process one Vapi server message and return the JSON body to reply with."""
