import uuid
from abc import ABC, abstractmethod

from app.models import Patient
from app.schemas.patient import PatientFilters


class IPatientRepository(ABC):
    """Persistence for patients. Soft-deleted rows are invisible to every method."""

    @abstractmethod
    def add(self, values: dict) -> Patient: ...

    @abstractmethod
    def get(self, patient_id: uuid.UUID) -> Patient | None: ...

    @abstractmethod
    def search(self, filters: PatientFilters) -> list[Patient]: ...

    @abstractmethod
    def update(self, patient_id: uuid.UUID, changes: dict) -> Patient | None: ...

    @abstractmethod
    def soft_delete(self, patient_id: uuid.UUID) -> Patient | None: ...

    @abstractmethod
    def find_by_phone(self, phone_number: str) -> list[Patient]: ...

    @abstractmethod
    def count(self) -> int: ...
