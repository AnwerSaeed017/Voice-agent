"""The REST API from the brief, through HTTP, against the real database."""

import uuid

import pytest

pytestmark = pytest.mark.integration


def assert_error(response, status: int, code: str | None = None) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["data"] is None and set(body) == {"data", "error"}
    if code:
        assert body["error"]["code"] == code
    return body["error"]


class TestCreate:
    def test_returns_the_created_record_in_the_envelope(self, client, patient_fields):
        fields = patient_fields(phone_number="(919) 555-0142", state="tx", sex="male", email="A@Example.com")
        response = client.post("/patients", json=fields)
        assert response.status_code == 201
        body = response.json()
        assert body["error"] is None
        patient = body["data"]
        assert uuid.UUID(patient["patient_id"])
        assert (patient["phone_number"], patient["state"], patient["sex"], patient["email"]) == ("9195550142", "TX", "Male", "a@example.com")
        assert patient["date_of_birth"] == "04/12/1988"
        assert patient["preferred_language"] == "English"
        assert patient["created_at"].endswith("Z") and patient["deleted_at"] is None

    @pytest.mark.parametrize("override, field", [
        ({"phone_number": "123"}, "phone_number"),
        ({"date_of_birth": "01/01/2999"}, "date_of_birth"),
        ({"date_of_birth": "02/30/1990"}, "date_of_birth"),
        ({"sex": "Robot"}, "sex"),
        ({"state": "ZZ"}, "state"),
        ({"zip_code": "12"}, "zip_code"),
        ({"email": "nope"}, "email"),
        ({"first_name": "J0e"}, "first_name"),
        ({"nickname": "JV"}, "nickname"),
    ])
    def test_invalid_field_is_rejected_and_named(self, client, patient_fields, override, field):
        fields = patient_fields(**override)
        error = assert_error(client.post("/patients", json=fields), 422, "validation_error")
        assert field in [detail["field"] for detail in error["details"]]
        assert client.get("/patients", params={"last_name": fields["last_name"]}).json()["data"] == []

    def test_malformed_json_is_a_bad_request(self, client):
        response = client.post("/patients", content="{not json", headers={"Content-Type": "application/json"})
        assert_error(response, 400, "bad_request")


class TestRead:
    def test_get_by_id(self, client, create_patient):
        patient = create_patient()
        assert client.get(f"/patients/{patient['patient_id']}").json()["data"] == patient

    def test_unknown_id_is_not_found(self, client):
        assert_error(client.get(f"/patients/{uuid.uuid4()}"), 404, "not_found")

    def test_malformed_id_is_a_bad_request(self, client):
        assert_error(client.get("/patients/12345"), 400, "bad_request")

    def test_filters_match_exactly(self, client, create_patient):
        patient = create_patient(date_of_birth="03/05/1990")
        other = create_patient()
        by_name = client.get("/patients", params={"last_name": patient["last_name"].upper()}).json()["data"]
        by_phone = client.get("/patients", params={"phone_number": patient["phone_number"]}).json()["data"]
        by_all = client.get("/patients", params={
            "last_name": patient["last_name"], "date_of_birth": "1990-03-05", "phone_number": patient["phone_number"]}).json()["data"]
        assert [entry["patient_id"] for entry in by_name] == [patient["patient_id"]]
        assert patient["patient_id"] in [entry["patient_id"] for entry in by_phone]
        assert [entry["patient_id"] for entry in by_all] == [patient["patient_id"]]
        assert other["patient_id"] not in [entry["patient_id"] for entry in by_name]

    def test_injection_attempt_in_a_filter_matches_nothing(self, client, create_patient):
        create_patient()
        assert client.get("/patients", params={"last_name": "' OR '1'='1"}).json()["data"] == []

    @pytest.mark.parametrize("params", [{"limit": "0"}, {"limit": "501"}, {"offset": "-1"}, {"date_of_birth": "soon"}, {"phone_number": "12"}])
    def test_invalid_filter_is_a_bad_request(self, client, params):
        assert_error(client.get("/patients", params=params), 400, "bad_request")


class TestUpdate:
    def test_partial_update_changes_only_what_was_sent(self, client, create_patient):
        patient = create_patient(email="keep@example.com")
        updated = client.put(f"/patients/{patient['patient_id']}", json={"city": "Chicago"}).json()["data"]
        assert updated["city"] == "Chicago" and updated["email"] == "keep@example.com"
        # Not strictly greater: two calls can land in the same clock tick.
        assert updated["updated_at"] >= patient["updated_at"] and updated["created_at"] == patient["created_at"]

    def test_optional_field_can_be_cleared(self, client, create_patient):
        patient = create_patient(email="gone@example.com")
        assert client.put(f"/patients/{patient['patient_id']}", json={"email": None}).json()["data"]["email"] is None

    def test_one_invalid_field_rejects_the_whole_update(self, client, create_patient):
        patient = create_patient()
        response = client.put(f"/patients/{patient['patient_id']}", json={"city": "Boston", "zip_code": "12"})
        assert_error(response, 422)
        assert client.get(f"/patients/{patient['patient_id']}").json()["data"]["city"] == "Springfield"

    def test_a_record_from_get_can_be_sent_back(self, client, create_patient):
        patient = create_patient()
        response = client.put(f"/patients/{patient['patient_id']}", json={**patient, "city": "Evanston", "patient_id": str(uuid.uuid4())})
        assert response.status_code == 200
        assert response.json()["data"]["patient_id"] == patient["patient_id"]

    def test_empty_body_is_rejected(self, client, create_patient):
        assert_error(client.put(f"/patients/{create_patient()['patient_id']}", json={}), 422)

    def test_unknown_patient(self, client):
        assert_error(client.put(f"/patients/{uuid.uuid4()}", json={"city": "X"}), 404)


class TestSoftDelete:
    def test_row_is_kept_but_hidden(self, client, container, create_patient):
        from app.models import Patient

        patient = create_patient()
        deleted = client.delete(f"/patients/{patient['patient_id']}")
        assert deleted.status_code == 200 and deleted.json()["data"]["deleted_at"] is not None
        assert_error(client.get(f"/patients/{patient['patient_id']}"), 404)
        assert client.get("/patients", params={"last_name": patient["last_name"]}).json()["data"] == []
        assert_error(client.put(f"/patients/{patient['patient_id']}", json={"city": "X"}), 404)
        assert_error(client.delete(f"/patients/{patient['patient_id']}"), 404)
        with container.database().session() as session:
            row = session.get(Patient, uuid.UUID(patient["patient_id"]))
            assert row is not None and row.deleted_at is not None


class TestMeta:
    def test_health_reports_the_database(self, client):
        assert client.get("/health").json() == {"data": {"status": "ok", "database": "ok"}, "error": None}

    def test_unknown_route_uses_the_envelope(self, client):
        assert_error(client.get("/no-such-route"), 404, "not_found")

    def test_console_is_served_with_a_content_security_policy(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "script-src 'self'" in response.headers["content-security-policy"]
        for path in ("/static/css/app.css", "/static/js/app.js", "/static/js/format.js"):
            assert client.get(path).status_code == 200
