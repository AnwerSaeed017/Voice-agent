from abc import ABC, abstractmethod
from datetime import date


class IFieldNormalizer(ABC):
    """Cleans and validates one field at a time. Every method raises ValueError with a
    message that is safe to show an API client or have the voice agent paraphrase."""

    @abstractmethod
    def clean_text(self, value: object) -> object: ...

    @abstractmethod
    def name(self, value: object) -> str | None: ...

    @abstractmethod
    def date_of_birth(self, value: object) -> date | None: ...

    @abstractmethod
    def sex(self, value: object) -> str | None: ...

    @abstractmethod
    def phone(self, value: object) -> str | None: ...

    @abstractmethod
    def email(self, value: object) -> str | None: ...

    @abstractmethod
    def state(self, value: object) -> str | None: ...

    @abstractmethod
    def zip_code(self, value: object) -> str | None: ...

    @abstractmethod
    def member_id(self, value: object) -> str | None: ...
