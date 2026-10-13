from datetime import datetime, timedelta, timezone

from app.schemas.dashboard import CallListQuery, Page, PatientListQuery
from app.services.dashboard_service import DashboardService
from app.tests.conftest import FixedClock

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


class FakePatients:
    def __init__(self, times=(), counts=None) -> None:
        self.times = list(times)
        self.counts = counts or {"total": 0, "with_email": 0, "with_insurance": 0,
                                 "with_emergency_contact": 0, "with_unit": 0, "voice": 0}
        self.asked_since = None
        self.query = None

    def registration_times(self, since):
        self.asked_since = since
        return [time for time in self.times if time >= since]

    def completeness_counts(self):
        return dict(self.counts)

    def search_page(self, query):
        self.query = query
        return Page(["patient"], 1)


class FakeCallLogs:
    def __init__(self, total=0, registered=0) -> None:
        self.total, self.registered = total, registered
        self.query = None

    def outcome_counts(self):
        return {"total": self.total, "registered": self.registered}

    def search_page(self, query):
        self.query = query
        return Page(["call"], 1)


def service(patients=None, call_logs=None) -> DashboardService:
    return DashboardService(patients or FakePatients(), call_logs or FakeCallLogs(), FixedClock(NOW))


def test_registrations_are_counted_per_day_and_end_today():
    times = [NOW - timedelta(hours=1), NOW - timedelta(hours=2), NOW - timedelta(days=3)]
    summary = service(FakePatients(times)).summary(days=7, utc_offset_minutes=0)
    series = {entry["date"]: entry["count"] for entry in summary["registrations"]}
    assert list(series) == [f"2026-10-{day:02d}" for day in range(7, 14)]
    assert series["2026-10-13"] == 2 and series["2026-10-10"] == 1
    assert sum(series.values()) == 3


def test_days_follow_the_viewers_time_zone():
    late_evening_utc = datetime(2026, 10, 12, 22, 30, tzinfo=timezone.utc)
    in_utc = service(FakePatients([late_evening_utc])).summary(7, 0)
    ahead = service(FakePatients([late_evening_utc])).summary(7, 300)
    assert {e["date"]: e["count"] for e in in_utc["registrations"]}["2026-10-12"] == 1
    assert {e["date"]: e["count"] for e in ahead["registrations"]}["2026-10-13"] == 1


def test_timestamps_in_another_zone_are_converted():
    karachi = timezone(timedelta(hours=5))
    local_time = datetime(2026, 10, 13, 2, 0, tzinfo=karachi)  # 21:00 UTC on the 12th
    summary = service(FakePatients([local_time])).summary(7, 0)
    assert {e["date"]: e["count"] for e in summary["registrations"]}["2026-10-12"] == 1
    assert summary["latest_registration_at"] == "2026-10-12T21:00:00Z"


def test_new_in_the_last_seven_days_is_independent_of_the_chart_range():
    times = [NOW - timedelta(days=1), NOW - timedelta(days=6), NOW - timedelta(days=8)]
    patients = FakePatients(times)
    summary = service(patients).summary(days=30, utc_offset_minutes=0)
    assert summary["patients"]["new_last_7_days"] == 2
    assert sum(entry["count"] for entry in summary["registrations"]) == 3
    assert patients.asked_since <= NOW - timedelta(days=29)


def test_derived_counts():
    counts = {"total": 10, "with_email": 4, "with_insurance": 3, "with_emergency_contact": 2, "with_unit": 1, "voice": 6}
    summary = service(FakePatients(counts=counts), FakeCallLogs(total=9, registered=7)).summary(7, 0)
    assert summary["patients"]["api"] == 4
    assert summary["calls"] == {"total": 9, "registered": 7, "not_registered": 2}
    assert summary["latest_registration_at"] is None


def test_lists_are_passed_to_the_repositories():
    patients, call_logs = FakePatients(), FakeCallLogs()
    dashboard = service(patients, call_logs)
    patient_query, call_query = PatientListQuery(q="doe", source="voice"), CallListQuery(outcome="registered")
    assert dashboard.list_patients(patient_query).items == ["patient"]
    assert dashboard.list_calls(call_query).total == 1
    assert patients.query is patient_query and call_logs.query is call_query
