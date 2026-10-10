import uuid
from abc import ABC, abstractmethod

from app.models import Patient
from app.schemas.patient import PatientCreate, PatientFilters, PatientUpdate


class IPatientService(ABC):
    """The single place patient business rules live. Used by both the REST routers and
    the voice agent, so a record saved by phone obeys exactly the same rules as the API."""

    @abstractmethod
    def create_patient(self, payload: PatientCreate) -> Patient: ...

    @abstractmethod
    def get_patient(self, patient_id: uuid.UUID) -> Patient: ...

    @abstractmethod
    def list_patients(self, filters: PatientFilters) -> list[Patient]: ...

    @abstractmethod
    def update_patient(self, patient_id: uuid.UUID, payload: PatientUpdate) -> Patient: ...

    @abstractmethod
    def delete_patient(self, patient_id: uuid.UUID) -> Patient: ...

    @abstractmethod
    def find_by_phone(self, phone_number: str) -> list[Patient]: ...
