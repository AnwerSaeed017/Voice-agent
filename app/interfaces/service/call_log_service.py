import uuid
from abc import ABC, abstractmethod

from app.models import CallLog


class ICallLogService(ABC):
    @abstractmethod
    def registered_patient_id(self, call_id: str | None) -> uuid.UUID | None:
        """The patient already saved during this call, if any."""

    @abstractmethod
    def record_registration(
        self, call_id: str | None, patient_id: uuid.UUID, caller_number: str | None, payload: dict
    ) -> None: ...

    @abstractmethod
    def record_call_end(
        self,
        call_id: str | None,
        caller_number: str | None,
        ended_reason: str | None,
        summary: str | None,
        transcript: str | None,
    ) -> CallLog | None: ...

    @abstractmethod
    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]: ...
