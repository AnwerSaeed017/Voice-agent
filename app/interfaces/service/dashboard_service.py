from abc import ABC, abstractmethod

from app.schemas.dashboard import CallListQuery, Page, PatientListQuery


class IDashboardService(ABC):
    """Read-only views for the web console. Changes still go through IPatientService."""

    @abstractmethod
    def summary(self, days: int, utc_offset_minutes: int) -> dict:
        """Headline numbers plus registrations per day, bucketed in the viewer's time zone."""

    @abstractmethod
    def list_patients(self, query: PatientListQuery) -> Page: ...

    @abstractmethod
    def list_calls(self, query: CallListQuery) -> Page: ...
