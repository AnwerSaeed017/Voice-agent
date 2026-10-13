"""The console's read endpoints, through HTTP, against the real database."""

import pytest

from app.tests.conftest import MARKER

pytestmark = pytest.mark.integration


def search(client, **params) -> dict:
    response = client.get("/dashboard/patients", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


class TestSummary:
    def test_shape_and_consistency(self, client, create_patient):
        create_patient(email="has@example.com")
        response = client.get("/dashboard/summary", params={"days": 7, "utc_offset_minutes": 0})
        assert response.status_code == 200 and response.json()["error"] is None
        summary = response.json()["data"]
        patients, calls = summary["patients"], summary["calls"]
        assert patients["voice"] + patients["api"] == patients["total"]
        assert calls["registered"] + calls["not_registered"] == calls["total"]
        assert patients["with_email"] >= 1 and patients["new_last_7_days"] >= 1
        assert len(summary["registrations"]) == 7 and summary["registrations"][-1]["count"] >= 1
        assert summary["latest_registration_at"].endswith("Z")

    @pytest.mark.parametrize("params", [{"days": 1}, {"days": 500}, {"utc_offset_minutes": 5000}])
    def test_invalid_parameters_are_rejected(self, client, params):
        assert client.get("/dashboard/summary", params=params).status_code == 422


class TestPatientSearch:
    def test_partial_match_on_name_email_city_and_phone(self, client, create_patient):
        patient = create_patient(email="findme@example.com", city="Kalamazoo", phone_number="9195557311")
        own = {"q": patient["last_name"]}
        assert [entry["patient_id"] for entry in search(client, **own)["items"]] == [patient["patient_id"]]
        for term in (patient["last_name"][3:11].upper(), f"jordan {patient['last_name']}"):
            assert patient["patient_id"] in [entry["patient_id"] for entry in search(client, q=term)["items"]]
        for term in ("FINDME@EX", "kalamaz", "(919) 555-7311"):
            assert patient["patient_id"] in [entry["patient_id"] for entry in search(client, q=term, limit=100)["items"]]

    def test_wildcard_characters_match_literally(self, client, create_patient):
        patient = create_patient(city="Fifty% Town")
        assert patient["patient_id"] in [entry["patient_id"] for entry in search(client, q="fifty% t")["items"]]
        assert search(client, q=f"{patient['last_name'][:8]}_")["total"] == 0

    def test_source_filter_and_call_count(self, client, call_tool, call_id, create_patient, patient_fields):
        by_api = create_patient()
        by_voice = call_tool("save_patient", {**patient_fields(), "read_back_confirmed": True}, call_id)
        voice = search(client, q=MARKER, source="voice", limit=100)["items"]
        api = search(client, q=MARKER, source="api", limit=100)["items"]
        assert by_voice["patient_id"] in [entry["patient_id"] for entry in voice]
        assert by_api["patient_id"] in [entry["patient_id"] for entry in api]
        assert all(entry["call_count"] >= 1 for entry in voice) and all(entry["call_count"] == 0 for entry in api)

    def test_sorting_and_paging(self, client, create_patient):
        for last_name in ("Pytestsortaaa", "Pytestsortbbb", "Pytestsortccc"):
            create_patient(last_name=last_name)
        ascending = [entry["last_name"] for entry in search(client, q="pytestsort", sort="name")["items"]]
        descending = [entry["last_name"] for entry in search(client, q="pytestsort", sort="name_desc")["items"]]
        assert ascending == sorted(ascending) and descending == ascending[::-1]
        page = search(client, q="pytestsort", sort="name", limit=1, offset=1)
        assert page["total"] == len(ascending) and [entry["last_name"] for entry in page["items"]] == [ascending[1]]

    def test_removed_patients_are_excluded(self, client, create_patient):
        patient = create_patient()
        client.delete(f"/patients/{patient['patient_id']}")
        assert search(client, q=patient["last_name"])["total"] == 0

    @pytest.mark.parametrize("params", [{"sort": "x"}, {"source": "fax"}, {"limit": 500}, {"offset": -1}])
    def test_invalid_parameters_are_rejected(self, client, params):
        assert client.get("/dashboard/patients", params=params).status_code == 422


class TestCallSearch:
    def test_lists_calls_with_the_patient_name_and_searches_transcripts(self, client, call_tool, end_call, call_id, patient_fields):
        fields = patient_fields()
        saved = call_tool("save_patient", {**fields, "read_back_confirmed": True}, call_id)
        end_call(call_id, transcript="AI: Hi.\nUser: My favourite word is quokkasaurus.")

        by_transcript = client.get("/dashboard/calls", params={"q": "QUOKKASAURUS"}).json()["data"]
        by_name = client.get("/dashboard/calls", params={"q": fields["last_name"]}).json()["data"]
        assert by_transcript["total"] == 1 and by_name["total"] == 1
        call = by_transcript["items"][0]
        assert (call["call_id"], call["registered"], call["patient_id"]) == (call_id, True, saved["patient_id"])
        assert call["patient_name"] == f"Jordan {fields['last_name']}"
        assert "collected_payload" not in call

    def test_name_is_hidden_once_the_patient_is_removed(self, client, call_tool, call_id, patient_fields):
        saved = call_tool("save_patient", {**patient_fields(), "read_back_confirmed": True}, call_id)
        client.delete(f"/patients/{saved['patient_id']}")
        calls = client.get("/dashboard/calls", params={"outcome": "registered", "limit": 100}).json()["data"]["items"]
        call = next(entry for entry in calls if entry["call_id"] == call_id)
        assert call["registered"] is True and call["patient_name"] is None

    def test_invalid_outcome_is_rejected(self, client):
        assert client.get("/dashboard/calls", params={"outcome": "maybe"}).status_code == 422
