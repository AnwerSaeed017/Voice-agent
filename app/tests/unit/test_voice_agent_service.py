"""The voice agent's tool handlers, with the patient and call-log services replaced by fakes."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.services.voice_agent_service import VoiceAgentService
from app.tests.conftest import FixedClock
from app.utilities.field_normalizer import FieldNormalizer
from app.utilities.validation_error_formatter import ValidationErrorFormatter

FIELDS = {
    "first_name": "Sam", "last_name": "Lee", "date_of_birth": "03/05/1990", "sex": "Male",
    "phone_number": "4155550100", "address_line_1": "1 Elm St", "city": "Austin",
    "state": "TX", "zip_code": "78701",
}
CONFIRMED = {**FIELDS, "read_back_confirmed": True}


class FakePatients:
    def __init__(self) -> None:
        self.records = {}
        self.fail_with = None

    def _store(self, patient_id, values):
        record = SimpleNamespace(patient_id=patient_id, **values)
        self.records[patient_id] = record
        return record

    def create_patient(self, payload):
        if self.fail_with:
            raise self.fail_with
        return self._store(uuid.uuid4(), payload.model_dump())

    def update_patient(self, patient_id, payload):
        if patient_id not in self.records:
            raise NotFoundError("No patient.")
        merged = {**vars(self.records[patient_id]), **payload.changes()}
        merged.pop("patient_id")
        return self._store(patient_id, merged)

    def find_by_phone(self, phone_number):
        return [record for record in self.records.values() if record.phone_number == phone_number]


class FakeCallLogs:
    def __init__(self) -> None:
        self.registered = {}
        self.ended = []

    def registered_patient_id(self, call_id):
        return self.registered.get(call_id)

    def record_registration(self, call_id, patient_id, caller_number, payload):
        self.registered[call_id] = patient_id

    def record_call_end(self, call_id, caller_number, ended_reason, summary, transcript):
        self.ended.append((call_id, ended_reason, summary, transcript))
        return SimpleNamespace(patient_id=self.registered.get(call_id))


@pytest.fixture
def agent():
    patients, call_logs = FakePatients(), FakeCallLogs()
    clock = FixedClock(datetime(2026, 1, 15, tzinfo=timezone.utc))
    service = VoiceAgentService(patients, call_logs, FieldNormalizer(clock), ValidationErrorFormatter())
    return SimpleNamespace(service=service, patients=patients, call_logs=call_logs)


def run(agent, name, arguments, call_id="call-1", **tool_call):
    message = {"type": "tool-calls", "call": {"id": call_id, "customer": {"number": "+14155550100"}},
               "toolCallList": [{"id": "t1", "name": name, "arguments": arguments, **tool_call}]}
    results = agent.service.handle_message(message)["results"]
    assert results[0]["toolCallId"] == "t1"
    return json.loads(results[0]["result"])


class TestSavePatient:
    def test_refused_until_the_read_back_is_confirmed(self, agent):
        result = run(agent, "save_patient", FIELDS)
        assert result["error_type"] == "confirmation_required"
        assert agent.patients.records == {}

    def test_confirmed_save_creates_the_patient_and_links_the_call(self, agent):
        result = run(agent, "save_patient", CONFIRMED)
        assert (result["success"], result["action"], result["first_name"]) == (True, "created", "Sam")
        assert str(agent.call_logs.registered["call-1"]) == result["patient_id"]

    def test_a_retry_in_the_same_call_updates_instead_of_duplicating(self, agent):
        first = run(agent, "save_patient", CONFIRMED)
        second = run(agent, "save_patient", {**CONFIRMED, "city": "Waco"})
        assert second["action"] == "updated" and second["patient_id"] == first["patient_id"]
        assert len(agent.patients.records) == 1
        assert agent.patients.records[uuid.UUID(first["patient_id"])].city == "Waco"

    def test_registers_again_when_the_first_record_was_deleted(self, agent):
        first = run(agent, "save_patient", CONFIRMED)
        agent.patients.records.clear()
        second = run(agent, "save_patient", CONFIRMED)
        assert second["action"] == "created" and second["patient_id"] != first["patient_id"]

    def test_invalid_details_are_reported_by_field_and_nothing_is_saved(self, agent):
        result = run(agent, "save_patient", {**CONFIRMED, "date_of_birth": "02/30/1990", "phone_number": "555"})
        assert result["error_type"] == "validation"
        assert {entry["field"] for entry in result["invalid_fields"]} == {"date_of_birth", "phone_number"}
        assert agent.patients.records == {}

    def test_validation_is_reported_before_the_confirmation_check(self, agent):
        assert run(agent, "save_patient", {**FIELDS, "zip_code": "12"})["error_type"] == "validation"

    def test_a_stray_argument_does_not_block_the_save(self, agent):
        assert run(agent, "save_patient", {**CONFIRMED, "confidence": 0.9})["success"] is True

    def test_a_database_failure_is_reported_as_a_system_error(self, agent):
        agent.patients.fail_with = RuntimeError("database is down")
        result = run(agent, "save_patient", CONFIRMED)
        assert (result["success"], result["error_type"]) == (False, "system")
        assert "database is down" not in json.dumps(result)


class TestCheckExistingPatient:
    def test_new_caller(self, agent):
        assert run(agent, "check_existing_patient", {"phone_number": "(415) 555-0100"}) == {"success": True, "found": False, "matches": []}

    def test_returning_caller_exposes_only_the_name(self, agent):
        saved = run(agent, "save_patient", CONFIRMED)
        result = run(agent, "check_existing_patient", {"phone_number": "4155550100"}, call_id="call-2")
        assert result["found"] is True
        assert result["matches"] == [{"patient_id": saved["patient_id"], "first_name": "Sam", "last_name": "Lee"}]

    @pytest.mark.parametrize("arguments", [{"phone_number": "123"}, {}])
    def test_invalid_or_missing_number(self, agent, arguments):
        result = run(agent, "check_existing_patient", arguments)
        assert result["error_type"] == "validation" and result["invalid_fields"][0]["field"] == "phone_number"


class TestUpdatePatient:
    def test_updates_only_the_changed_details(self, agent):
        saved = run(agent, "save_patient", CONFIRMED)
        result = run(agent, "update_patient", {"patient_id": saved["patient_id"], "zip_code": "76701", "read_back_confirmed": True}, call_id="call-2")
        record = agent.patients.records[uuid.UUID(saved["patient_id"])]
        assert result["action"] == "updated" and (record.zip_code, record.city) == ("76701", "Austin")

    def test_refused_without_confirmation(self, agent):
        saved = run(agent, "save_patient", CONFIRMED)
        result = run(agent, "update_patient", {"patient_id": saved["patient_id"], "city": "Waco"})
        assert result["error_type"] == "confirmation_required"

    def test_unknown_record(self, agent):
        result = run(agent, "update_patient", {"patient_id": str(uuid.uuid4()), "city": "Waco", "read_back_confirmed": True})
        assert result["error_type"] == "not_found"

    def test_malformed_patient_id(self, agent):
        assert run(agent, "update_patient", {"patient_id": "abc", "city": "Waco"})["error_type"] == "system"


class TestMessageHandling:
    def test_unknown_tool(self, agent):
        assert run(agent, "book_flight", {})["error_type"] == "system"

    def test_arguments_sent_as_a_json_string(self, agent):
        message = {"type": "tool-calls", "call": {"id": "c"}, "toolCallList": [
            {"id": "t1", "function": {"name": "check_existing_patient", "arguments": json.dumps({"phone_number": "4155550100"})}}]}
        result = json.loads(agent.service.handle_message(message)["results"][0]["result"])
        assert result["success"] is True

    def test_unparseable_arguments_become_a_validation_failure(self, agent):
        assert run(agent, "save_patient", "{broken")["error_type"] == "validation"

    def test_several_tool_calls_get_one_result_each(self, agent):
        message = {"type": "tool-calls", "call": {"id": "c"}, "toolCallList": [
            {"id": "a", "name": "check_existing_patient", "arguments": {"phone_number": "4155550100"}},
            {"id": "b", "name": "check_existing_patient", "arguments": {"phone_number": "12"}}]}
        assert [entry["toolCallId"] for entry in agent.service.handle_message(message)["results"]] == ["a", "b"]

    def test_end_of_call_report_is_recorded(self, agent):
        reply = agent.service.handle_message({
            "type": "end-of-call-report", "endedReason": "customer-ended-call", "transcript": "AI: Hi.",
            "analysis": {"summary": "Dropped."}, "call": {"id": "call-9"}})
        assert reply == {}
        assert agent.call_logs.ended == [("call-9", "customer-ended-call", "Dropped.", "AI: Hi.")]

    @pytest.mark.parametrize("message", [{}, {"type": "status-update"}, {"type": "tool-calls"}])
    def test_other_messages_are_acknowledged(self, agent, message):
        assert agent.service.handle_message(message) in ({}, {"results": []})
