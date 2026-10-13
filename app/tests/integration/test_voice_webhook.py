"""The Vapi webhook end to end: tool calls in, rows in the database out."""

import pytest

pytestmark = pytest.mark.integration


def rows_with_phone(client, phone_number: str) -> list[dict]:
    return client.get("/patients", params={"phone_number": phone_number}).json()["data"]


class TestAuthentication:
    def test_missing_or_wrong_secret_is_refused(self, client):
        assert client.post("/vapi/webhook", json={"message": {}}).status_code == 401
        assert client.post("/vapi/webhook", json={"message": {}}, headers={"X-Vapi-Secret": "wrong"}).status_code == 401

    def test_unrelated_message_is_acknowledged(self, webhook):
        response = webhook({"type": "status-update"})
        assert response.status_code == 200 and response.json() == {}


class TestRegistrationCall:
    def test_nothing_is_saved_before_confirmation(self, client, call_tool, call_id, patient_fields):
        fields = patient_fields()
        result = call_tool("save_patient", fields, call_id)
        assert result["error_type"] == "confirmation_required"
        assert rows_with_phone(client, fields["phone_number"]) == []

    def test_confirmed_registration_is_stored_and_linked_to_the_call(self, client, call_tool, end_call, call_id, patient_fields):
        fields = patient_fields(state="Illinois", email="")
        result = call_tool("save_patient", {**fields, "read_back_confirmed": True}, call_id)
        assert result["success"] and result["action"] == "created"
        stored = client.get(f"/patients/{result['patient_id']}").json()["data"]
        assert (stored["state"], stored["email"], stored["last_name"]) == ("IL", None, fields["last_name"])

        end_call(call_id, transcript="AI: You're all set.\nUser: Thanks.")
        calls = client.get(f"/patients/{result['patient_id']}/calls").json()["data"]
        assert [(call["call_id"], call["transcript"], call["summary"]) for call in calls] == [
            (call_id, "AI: You're all set.\nUser: Thanks.", "Test call.")]

    def test_retry_in_the_same_call_does_not_duplicate(self, client, call_tool, call_id, patient_fields):
        fields = {**patient_fields(), "read_back_confirmed": True}
        first = call_tool("save_patient", fields, call_id)
        second = call_tool("save_patient", {**fields, "city": "Peoria"}, call_id)
        assert second["action"] == "updated" and second["patient_id"] == first["patient_id"]
        rows = rows_with_phone(client, fields["phone_number"])
        assert len(rows) == 1 and rows[0]["city"] == "Peoria"

    def test_invalid_details_are_reported_and_nothing_is_saved(self, client, call_tool, call_id, patient_fields):
        fields = patient_fields()
        result = call_tool("save_patient", {**fields, "date_of_birth": "02/30/1990", "read_back_confirmed": True}, call_id)
        assert result["error_type"] == "validation"
        assert [entry["field"] for entry in result["invalid_fields"]] == ["date_of_birth"]
        assert rows_with_phone(client, fields["phone_number"]) == []

    def test_dropped_call_is_logged_without_a_patient(self, client, end_call, call_id):
        end_call(call_id, reason="customer-ended-call")
        calls = client.get("/dashboard/calls", params={"outcome": "not_registered", "limit": 100}).json()["data"]["items"]
        dropped = next(call for call in calls if call["call_id"] == call_id)
        assert dropped["registered"] is False and dropped["patient_id"] is None


class TestReturningCaller:
    def test_is_recognised_by_phone_and_only_the_name_is_exposed(self, call_tool, call_id, create_patient):
        patient = create_patient()
        result = call_tool("check_existing_patient", {"phone_number": patient["phone_number"]}, call_id)
        match = next(entry for entry in result["matches"] if entry["patient_id"] == patient["patient_id"])
        assert result["found"] is True
        assert match == {"patient_id": patient["patient_id"], "first_name": "Jordan", "last_name": patient["last_name"]}

    def test_update_changes_only_what_the_caller_gave(self, client, call_tool, call_id, create_patient):
        patient = create_patient()
        result = call_tool("update_patient", {
            "patient_id": patient["patient_id"], "address_line_1": "9 Oak Avenue", "zip_code": "61602",
            "read_back_confirmed": True}, call_id)
        stored = client.get(f"/patients/{patient['patient_id']}").json()["data"]
        assert result["action"] == "updated"
        assert (stored["address_line_1"], stored["zip_code"], stored["city"]) == ("9 Oak Avenue", "61602", "Springfield")

    def test_update_of_a_removed_record_tells_the_agent(self, client, call_tool, call_id, create_patient):
        patient = create_patient()
        client.delete(f"/patients/{patient['patient_id']}")
        result = call_tool("update_patient", {"patient_id": patient["patient_id"], "city": "X", "read_back_confirmed": True}, call_id)
        assert result["error_type"] == "not_found"
