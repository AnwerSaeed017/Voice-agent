import uuid

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.interfaces.repository import IPatientRepository
from app.interfaces.service import IPatientService
from app.models import Patient
from app.schemas.patient import PatientCreate, PatientFilters, PatientUpdate


class PatientService(IPatientService):
    def __init__(self, patients: IPatientRepository) -> None:
        self._patients = patients

    def create_patient(self, payload: PatientCreate) -> Patient:
        return self._patients.add(payload.model_dump())

    def get_patient(self, patient_id: uuid.UUID) -> Patient:
        return self._found(self._patients.get(patient_id), patient_id)

    def list_patients(self, filters: PatientFilters) -> list[Patient]:
        return self._patients.search(filters)

    def update_patient(self, patient_id: uuid.UUID, payload: PatientUpdate) -> Patient:
        changes = payload.changes()
        if not changes:
            raise ValidationFailedError(
                "Provide at least one field to update.",
                [{"field": "body", "message": "No fields were provided."}],
            )
        return self._found(self._patients.update(patient_id, changes), patient_id)

    def delete_patient(self, patient_id: uuid.UUID) -> Patient:
        return self._found(self._patients.soft_delete(patient_id), patient_id)

    def find_by_phone(self, phone_number: str) -> list[Patient]:
        return self._patients.find_by_phone(phone_number)

    @staticmethod
    def _found(patient: Patient | None, patient_id: uuid.UUID) -> Patient:
        if patient is None:
            raise NotFoundError(f"No patient found with id {patient_id}.")
        return patient
