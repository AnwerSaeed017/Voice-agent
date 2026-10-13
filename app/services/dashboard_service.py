from datetime import datetime, timedelta, timezone

from app.constants.constants import WEEK
from app.interfaces.repository import ICallLogRepository, IPatientRepository
from app.interfaces.service import IDashboardService
from app.interfaces.utilities import IClock
from app.schemas.dashboard import CallListQuery, Page, PatientListQuery


class DashboardService(IDashboardService):
    def __init__(
        self, patients: IPatientRepository, call_logs: ICallLogRepository, clock: IClock
    ) -> None:
        self._patients = patients
        self._call_logs = call_logs
        self._clock = clock

    def summary(self, days: int, utc_offset_minutes: int) -> dict:
        now = self._clock.utc_now()
        offset = timedelta(minutes=utc_offset_minutes)
        today = (now + offset).date()
        first_day = today - timedelta(days=days - 1)
        # Start of the first charted day in the viewer's zone, expressed in UTC.
        range_start = datetime.combine(first_day, datetime.min.time(), timezone.utc) - offset
        week_start = now - WEEK

        per_day = {first_day + timedelta(days=index): 0 for index in range(days)}
        new_this_week = 0
        latest = None
        for created_at in self._patients.registration_times(min(range_start, week_start)):
            created_at = self._as_utc(created_at)
            if created_at >= week_start:
                new_this_week += 1
            local_day = (created_at + offset).date()
            if local_day in per_day:
                per_day[local_day] += 1
            if latest is None or created_at > latest:
                latest = created_at

        patients = self._patients.completeness_counts()
        calls = self._call_logs.outcome_counts()
        return {
            "patients": {
                **patients,
                "api": patients["total"] - patients["voice"],
                "new_last_7_days": new_this_week,
            },
            "calls": {**calls, "not_registered": calls["total"] - calls["registered"]},
            "registrations": [
                {"date": day.isoformat(), "count": count} for day, count in per_day.items()
            ],
            "latest_registration_at": (
                latest.isoformat().replace("+00:00", "Z") if latest else None
            ),
        }

    def list_patients(self, query: PatientListQuery) -> Page:
        return self._patients.search_page(query)

    def list_calls(self, query: CallListQuery) -> Page:
        return self._call_logs.search_page(query)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        # The driver returns timestamps in the database session's time zone.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
