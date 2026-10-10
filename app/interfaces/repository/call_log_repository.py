import uuid
from abc import ABC, abstractmethod

from app.models import CallLog


class ICallLogRepository(ABC):
    @abstractmethod
    def get(self, call_id: str) -> CallLog | None: ...

    @abstractmethod
    def upsert(self, call_id: str, values: dict) -> CallLog: ...

    @abstractmethod
    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]: ...
