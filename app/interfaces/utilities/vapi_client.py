from abc import ABC, abstractmethod


class IVapiClient(ABC):
    @abstractmethod
    def list_assistants(self) -> list[dict]: ...

    @abstractmethod
    def create_assistant(self, config: dict) -> dict: ...

    @abstractmethod
    def update_assistant(self, assistant_id: str, config: dict) -> dict: ...

    @abstractmethod
    def list_phone_numbers(self) -> list[dict]: ...

    @abstractmethod
    def create_phone_number(self, config: dict) -> dict: ...

    @abstractmethod
    def update_phone_number(self, phone_number_id: str, config: dict) -> dict: ...
