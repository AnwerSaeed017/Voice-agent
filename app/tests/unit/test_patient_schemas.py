from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientCreate, PatientFilters, PatientUpdate

VALID = {
    "first_name": "Sam", "last_name": "Lee", "date_of_birth": "03/05/1990", "sex": "male",
    "phone_number": "(415) 555-0100", "address_line_1": "1 Elm St", "city": "Austin",
    "state": "Texas", "zip_code": "787014321",
}


def invalid_fields(error: ValidationError) -> set[str]:
    return {str(entry["loc"][0]) for entry in error.errors()}


class TestPatientCreate:
    def test_normalises_every_field(self):
        patient = PatientCreate(**VALID, email="SAM@Example.com")
        assert patient.date_of_birth == date(1990, 3, 5)
        assert (patient.sex, patient.phone_number, patient.state, patient.zip_code) == ("Male", "4155550100", "TX", "78701-4321")
        assert patient.email == "sam@example.com"
        assert patient.preferred_language == "English"

    def test_reports_every_missing_required_field(self):
        with pytest.raises(ValidationError) as caught:
            PatientCreate()
        assert invalid_fields(caught.value) == {
            "first_name", "last_name", "date_of_birth", "sex", "phone_number",
            "address_line_1", "city", "state", "zip_code",
        }

    def test_reports_all_invalid_fields_at_once(self):
        with pytest.raises(ValidationError) as caught:
            PatientCreate(**{**VALID, "phone_number": "12", "state": "ZZ", "zip_code": "1"})
        assert invalid_fields(caught.value) == {"phone_number", "state", "zip_code"}

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError) as caught:
            PatientCreate(**VALID, favourite_colour="blue")
        assert invalid_fields(caught.value) == {"favourite_colour"}

    def test_server_managed_fields_are_ignored(self):
        patient = PatientCreate(**VALID, patient_id="x", created_at="y", updated_at="z", deleted_at=None)
        assert "patient_id" not in patient.model_dump()

    def test_empty_optional_text_is_stored_as_none(self):
        assert PatientCreate(**VALID, email="  ", address_line_2="").email is None

    def test_future_date_of_birth_is_rejected(self):
        with pytest.raises(ValidationError) as caught:
            PatientCreate(**{**VALID, "date_of_birth": "01/01/2999"})
        assert invalid_fields(caught.value) == {"date_of_birth"}

    @pytest.mark.parametrize("field, length", [("address_line_1", 201), ("address_line_2", 101), ("city", 101)])
    def test_length_limits(self, field, length):
        with pytest.raises(ValidationError):
            PatientCreate(**{**VALID, field: "x" * length})


class TestPatientUpdate:
    def test_changes_holds_only_the_fields_sent(self):
        assert PatientUpdate(city="Waco").changes() == {"city": "Waco"}

    def test_optional_field_can_be_cleared(self):
        assert PatientUpdate(email=None).changes() == {"email": None}

    def test_required_field_cannot_be_cleared(self):
        with pytest.raises(ValidationError) as caught:
            PatientUpdate(last_name=None)
        assert invalid_fields(caught.value) == {"last_name"}

    def test_values_are_normalised(self):
        assert PatientUpdate(state="ny", phone_number="919-555-0777").changes() == {"state": "NY", "phone_number": "9195550777"}


class TestPatientFilters:
    def test_defaults(self):
        filters = PatientFilters()
        assert (filters.limit, filters.offset) == (100, 0)

    @pytest.mark.parametrize("values", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"phone_number": "12"}, {"date_of_birth": "soon"}])
    def test_rejects_invalid_values(self, values):
        with pytest.raises(ValidationError):
            PatientFilters(**values)
