import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.interfaces.repository import IPatientRepository
from app.interfaces.utilities import IClock, IDatabase
from app.models import Patient
from app.schemas.patient import PatientFilters


class PatientRepository(IPatientRepository):
    """All SQL for the patients table. Soft-deleted rows are filtered out everywhere."""

    def __init__(self, database: IDatabase, clock: IClock) -> None:
        self._database = database
        self._clock = clock

    def add(self, values: dict) -> Patient:
        now = self._clock.utc_now()
        patient = Patient(**values, created_at=now, updated_at=now)
        with self._database.session() as session:
            session.add(patient)
        return patient

    def get(self, patient_id: uuid.UUID) -> Patient | None:
        with self._database.session() as session:
            return self._get_active(session, patient_id)

    def search(self, filters: PatientFilters) -> list[Patient]:
        statement = select(Patient).where(Patient.deleted_at.is_(None))
        if filters.last_name:
            statement = statement.where(
                func.lower(Patient.last_name) == filters.last_name.lower()
            )
        if filters.date_of_birth:
            statement = statement.where(Patient.date_of_birth == filters.date_of_birth)
        if filters.phone_number:
            statement = statement.where(Patient.phone_number == filters.phone_number)
        statement = (
            statement.order_by(Patient.created_at.desc(), Patient.patient_id)
            .limit(filters.limit)
            .offset(filters.offset)
        )
        with self._database.session() as session:
            return list(session.scalars(statement))

    def update(self, patient_id: uuid.UUID, changes: dict) -> Patient | None:
        with self._database.session() as session:
            patient = self._get_active(session, patient_id)
            if patient is None:
                return None
            for field, value in changes.items():
                setattr(patient, field, value)
            patient.updated_at = self._clock.utc_now()
            return patient

    def soft_delete(self, patient_id: uuid.UUID) -> Patient | None:
        with self._database.session() as session:
            patient = self._get_active(session, patient_id)
            if patient is None:
                return None
            now = self._clock.utc_now()
            patient.deleted_at = now
            patient.updated_at = now
            return patient

    def find_by_phone(self, phone_number: str) -> list[Patient]:
        statement = (
            select(Patient)
            .where(Patient.deleted_at.is_(None), Patient.phone_number == phone_number)
            .order_by(Patient.updated_at.desc())
        )
        with self._database.session() as session:
            return list(session.scalars(statement))

    def count(self) -> int:
        statement = select(func.count()).select_from(Patient)
        with self._database.session() as session:
            return session.scalar(statement) or 0

    @staticmethod
    def _get_active(session: Session, patient_id: uuid.UUID) -> Patient | None:
        statement = select(Patient).where(
            Patient.patient_id == patient_id, Patient.deleted_at.is_(None)
        )
        return session.scalars(statement).first()
