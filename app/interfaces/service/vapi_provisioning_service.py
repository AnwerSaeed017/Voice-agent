from abc import ABC, abstractmethod


class IVapiProvisioningService(ABC):
    @abstractmethod
    def sync_assistant(self) -> dict:
        """Create the Vapi assistant, or update it in place if it already exists."""

    @abstractmethod
    def ensure_phone_number(self, assistant_id: str) -> dict:
        """Attach a phone number to the assistant, buying one if the account has none."""
