import uuid
from abc import ABC, abstractmethod

from app.models import CallLog
from app.schemas.dashboard import CallListQuery, Page


class ICallLogRepository(ABC):
    @abstractmethod
    def get(self, call_id: str) -> CallLog | None: ...

    @abstractmethod
    def upsert(self, call_id: str, values: dict) -> CallLog: ...

    @abstractmethod
    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]: ...

    @abstractmethod
    def search_page(self, query: CallListQuery) -> Page:
        """Every call, newest first. Items are (call, name of its active patient or None)."""

    @abstractmethod
    def outcome_counts(self) -> dict[str, int]:
        """Total calls, and how many ended with a patient record."""
