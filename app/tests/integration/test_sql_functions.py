"""The repositories against the real database: each call runs a SQL function from app/sql/functions."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.constants.constants import UPSERT_FIELDS
from app.schemas.patient import PatientCreate

pytestmark = pytest.mark.integration


@pytest.fixture
def patients(container, clean_database):
    return container.repositories.patient_repository()


@pytest.fixture
def call_logs(container, clean_database):
    return container.repositories.call_log_repository()


@pytest.fixture
def values(patient_fields):
    return lambda **overrides: PatientCreate(**patient_fields(**overrides)).model_dump()


class TestPatientFunctions:
    def test_add_sets_the_id_and_both_timestamps(self, patients, values):
        patient = patients.add(values())
        assert isinstance(patient.patient_id, uuid.UUID)
        assert patient.created_at == patient.updated_at and patient.deleted_at is None
        assert patients.get(patient.patient_id).last_name == patient.last_name

    def test_update_leaves_absent_fields_and_clears_null_ones(self, patients, values):
        patient = patients.add(values(email="x@example.com", address_line_2="Apt 1"))
        updated = patients.update(patient.patient_id, {"email": None, "city": "Waco"})
        assert (updated.email, updated.city, updated.address_line_2) == (None, "Waco", "Apt 1")
        assert updated.updated_at >= patient.updated_at and updated.created_at == patient.created_at

    def test_soft_delete_hides_the_row_from_every_read(self, patients, values):
        patient = patients.add(values())
        assert patients.soft_delete(patient.patient_id).deleted_at is not None
        assert patients.get(patient.patient_id) is None
        assert patients.find_by_phone(patient.phone_number) == []
        assert patients.update(patient.patient_id, {"city": "X"}) is None
        assert patients.soft_delete(patient.patient_id) is None

    def test_database_constraints_still_apply_inside_the_function(self, patients, values):
        with pytest.raises(DBAPIError):
            patients.add({**values(), "sex": "Robot"})
        with pytest.raises(DBAPIError):
            patients.add({**values(), "phone_number": "123"})

    def test_count_includes_removed_rows(self, patients, values):
        before = patients.count()
        patients.soft_delete(patients.add(values()).patient_id)
        assert patients.count() == before + 1


class TestCallLogFunctions:
    def test_upsert_never_overwrites_a_value_with_nothing(self, call_logs, call_id):
        call_logs.upsert(call_id, {"caller_number": "+19195550100", "collected_payload": {"city": "Austin"}})
        merged = call_logs.upsert(call_id, {"summary": "Done.", "caller_number": None})
        assert (merged.caller_number, merged.summary, merged.collected_payload) == ("+19195550100", "Done.", {"city": "Austin"})
        assert merged.updated_at >= merged.created_at
        assert call_logs.get(call_id).summary == "Done."

    def test_upsert_fields_match_the_function_arguments(self, container, clean_database):
        arguments = container.database().execute_scalar(
            "SELECT pg_get_function_arguments('call_log_upsert'::regproc)")
        for field in UPSERT_FIELDS:
            assert f"p_{field} " in arguments

    def test_call_must_reference_an_existing_patient(self, call_logs, call_id):
        with pytest.raises(DBAPIError):
            call_logs.upsert(call_id, {"patient_id": uuid.uuid4()})


def test_every_function_is_installed(container, clean_database):
    with container.database().session() as session:
        installed = set(session.execute(text(
            "SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace")).scalars())
    assert {"patient_add", "patient_update", "patient_search_page", "call_log_upsert", "call_log_search_page"} <= installed
    assert len(installed) >= 18
