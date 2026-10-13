import importlib.util
import json
import re
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestError
from app.database.database import Database
from app.schemas.patient import PatientCreate
from app.utilities.request_parser import RequestParser
from app.utilities.response_builder import ResponseBuilder
from app.utilities.secret_verifier import SharedSecretVerifier
from app.utilities.validation_error_formatter import ValidationErrorFormatter

ROOT = Path(__file__).resolve().parents[3]


class TestValidationErrorFormatter:
    def errors(self, **fields) -> list[dict]:
        with pytest.raises(ValidationError) as caught:
            PatientCreate(**fields)
        return ValidationErrorFormatter().format(caught.value.errors())

    def test_missing_field_reads_as_required(self):
        formatted = {entry["field"]: entry["message"] for entry in self.errors()}
        assert formatted["first_name"] == "This field is required."

    def test_custom_message_is_cleaned_and_capitalised(self):
        formatted = {entry["field"]: entry["message"] for entry in self.errors(phone_number="123")}
        assert formatted["phone_number"] == "Must be a 10-digit U.S. phone number (received 3 digits)"

    def test_unknown_field(self):
        formatted = {entry["field"]: entry["message"] for entry in self.errors(nickname="JV")}
        assert formatted["nickname"] == "Unknown field."

    def test_request_location_prefix_is_dropped(self):
        formatted = ValidationErrorFormatter().format([{"loc": ("body", "city"), "type": "x", "msg": "bad"}])
        assert formatted == [{"field": "city", "message": "Bad"}]


class TestResponseBuilder:
    def test_success_envelope(self):
        response = ResponseBuilder().success({"a": 1}, 201)
        assert response.status_code == 201
        assert json.loads(response.body) == {"data": {"a": 1}, "error": None}

    def test_error_envelope(self):
        response = ResponseBuilder().error(404, "not_found", "No patient.")
        assert json.loads(response.body) == {"data": None, "error": {"code": "not_found", "message": "No patient.", "details": []}}


class TestRequestParser:
    parser = RequestParser(ValidationErrorFormatter())

    def test_valid_uuid(self):
        value = uuid.uuid4()
        assert self.parser.patient_id(str(value).upper()) == value

    def test_malformed_id_is_a_bad_request(self):
        with pytest.raises(BadRequestError):
            self.parser.patient_id("12345")

    def test_filters_skip_missing_values(self):
        filters = self.parser.patient_filters({"last_name": "Doe", "limit": None, "phone_number": None})
        assert (filters.last_name, filters.limit) == ("Doe", 100)

    def test_invalid_filter_is_a_bad_request_naming_the_field(self):
        with pytest.raises(BadRequestError) as caught:
            self.parser.patient_filters({"limit": "0"})
        assert caught.value.details[0]["field"] == "limit"


class TestSharedSecretVerifier:
    def test_accepts_only_the_expected_secret(self):
        verifier = SharedSecretVerifier(expected="s3cret")
        assert verifier.is_valid("s3cret")
        assert not verifier.is_valid("wrong")
        assert not verifier.is_valid(None)


class TestDatabase:
    def test_refuses_a_non_postgresql_url(self):
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            Database("sqlite:///./patients.db")

    @pytest.mark.parametrize("function, arguments", [
        ("patient_get; DROP TABLE patients", {}),
        ("Patient_Get", {}),
        ("patient_get", {"p_id); --": 1}),
    ])
    def test_rejects_unsafe_identifiers_before_touching_the_database(self, function, arguments):
        # The engine is lazy: an unreachable host proves no connection was attempted.
        database = Database("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
        with pytest.raises(ValueError, match="identifier"):
            database.call(function, **arguments)


class TestSqlFunctionFiles:
    """The migration splits the SQL files itself, so its splitter is tested here."""

    @pytest.fixture(scope="class")
    def migration(self):
        path = ROOT / "alembic" / "versions" / "0002_load_sql_functions.py"
        spec = importlib.util.spec_from_file_location("load_sql_functions", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def created(self, migration) -> list[str]:
        names = []
        for name in migration.FUNCTION_FILES:
            for statement in migration.statements(name):
                assert statement.rstrip().endswith("$$;"), statement[:60]
                names.append(re.match(r"CREATE OR REPLACE FUNCTION (\w+)", statement).group(1))
        return names

    def test_each_file_splits_into_whole_function_definitions(self, migration):
        assert len(self.created(migration)) == 18

    def test_downgrade_drops_exactly_the_functions_that_are_created(self, migration):
        dropped = [re.match(r"DROP FUNCTION IF EXISTS (\w+);", statement).group(1) for statement in migration.statements("drop")]
        assert sorted(dropped) == sorted(self.created(migration))

    def test_function_files_avoid_characters_the_migration_cannot_run(self, migration):
        # A lone colon would be read as a bind parameter, a percent sign as a driver placeholder.
        for name in (*migration.FUNCTION_FILES, "drop"):
            for statement in migration.statements(name):
                assert "%" not in statement
                assert not re.search(r"(?<!:):\w", statement), statement[:80]
