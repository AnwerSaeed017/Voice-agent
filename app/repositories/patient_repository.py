import json
import uuid
from datetime import datetime

from app.interfaces.repository import IPatientRepository
from app.interfaces.utilities import IClock, IDatabase
from app.models import Patient
from app.schemas.dashboard import Page, PatientListQuery
from app.schemas.patient import PatientFilters


class PatientRepository(IPatientRepository):
    """Persistence for patients. Every operation is a SQL function defined in
    app/sql/functions/patients.sql; no SQL is written here."""

    def __init__(self, database: IDatabase, clock: IClock) -> None:
        self._database = database
        self._clock = clock

    def add(self, values: dict) -> Patient:
        rows = self._database.call(
            "patient_add", p_values=self._as_json(values), p_now=self._clock.utc_now()
        )
        return Patient(**rows[0])

    def get(self, patient_id: uuid.UUID) -> Patient | None:
        return self._first(self._database.call("patient_get", p_patient_id=patient_id))

    def search(self, filters: PatientFilters) -> list[Patient]:
        rows = self._database.call(
            "patient_search",
            p_last_name=filters.last_name,
            p_date_of_birth=filters.date_of_birth,
            p_phone_number=filters.phone_number,
            p_limit=filters.limit,
            p_offset=filters.offset,
        )
        return [Patient(**row) for row in rows]

    def update(self, patient_id: uuid.UUID, changes: dict) -> Patient | None:
        rows = self._database.call(
            "patient_update",
            p_patient_id=patient_id,
            p_changes=self._as_json(changes),
            p_now=self._clock.utc_now(),
        )
        return self._first(rows)

    def soft_delete(self, patient_id: uuid.UUID) -> Patient | None:
        rows = self._database.call(
            "patient_soft_delete", p_patient_id=patient_id, p_now=self._clock.utc_now()
        )
        return self._first(rows)

    def find_by_phone(self, phone_number: str) -> list[Patient]:
        rows = self._database.call("patient_find_by_phone", p_phone_number=phone_number)
        return [Patient(**row) for row in rows]

    def count(self) -> int:
        return int(self._database.call_value("patient_count") or 0)

    def search_page(self, query: PatientListQuery) -> Page:
        rows = self._database.call(
            "patient_search_page",
            p_q=query.q,
            p_source=query.source,
            p_sort=query.sort,
            p_limit=query.limit,
            p_offset=query.offset,
        )
        total = self._database.call_value(
            "patient_search_page_count", p_q=query.q, p_source=query.source
        )
        patients = [Patient(**row) for row in rows]
        call_counts = {}
        if patients:
            counted = self._database.call(
                "patient_call_counts",
                p_patient_ids=[str(patient.patient_id) for patient in patients],
            )
            call_counts = {row["patient_id"]: int(row["call_count"]) for row in counted}
        items = [(patient, call_counts.get(patient.patient_id, 0)) for patient in patients]
        return Page(items, int(total or 0))

    def completeness_counts(self) -> dict[str, int]:
        row = self._database.call("patient_completeness_counts")[0]
        return {name: int(value) for name, value in row.items()}

    def registration_times(self, since: datetime) -> list[datetime]:
        rows = self._database.call("patient_registration_times", p_since=since)
        return [next(iter(row.values())) for row in rows]

    @staticmethod
    def _first(rows: list) -> Patient | None:
        return Patient(**rows[0]) if rows else None

    @staticmethod
    def _as_json(values: dict) -> str:
        # Dates travel as ISO strings; the function casts them back to the column type.
        return json.dumps(values, default=str)
