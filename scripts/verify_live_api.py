"""Verify every endpoint of a running server, cross-check each result in the database,
and write the outcome to docs/api_verification.md.

    python -m scripts.verify_live_api                      # http://localhost:8000
    python -m scripts.verify_live_api --base-url https://your-app.up.railway.app

The script must be able to reach the same database as the server (DATABASE_URL), because
every write is confirmed by reading the row back directly. All rows it creates carry the
last name "Verify..." or a call id starting "verify-", and are removed at the end. The
migration checks create and drop a throwaway database on the same PostgreSQL server.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.containers.container import Container
from app.models import CallLog, Patient
from app.schemas.patient import PatientCreate


class LiveApiVerifier:
    REPORT_FILE = Path(__file__).resolve().parents[1] / "docs" / "api_verification.md"
    MARKER = "Verify"
    CALL_PREFIX = "verify-"
    UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self._base_url, timeout=20)
        self._container = Container()
        self._database = self._container.database()
        self._secret = self._container.settings().vapi_webhook_secret
        self._results: list[dict] = []
        self._next_phone = 9195550100

    # --- entry point ---------------------------------------------------------------

    def run(self) -> int:
        self._remove_test_rows()
        self._verify_meta()
        self._verify_create()
        self._verify_create_validation()
        self._verify_read()
        self._verify_list()
        self._verify_update()
        self._verify_delete()
        self._verify_voice_webhook()
        self._verify_boundaries()
        self._verify_webhook_robustness()
        self._verify_http_behaviour()
        self._verify_concurrency()
        self._verify_database_constraints()
        self._verify_restart_persistence()
        self._verify_migrations()
        self._verify_failure_handling()
        removed = self._remove_test_rows()
        self._write_report(removed)

        failed = [result for result in self._results if not result["passed"]]
        print(f"{len(self._results) - len(failed)} passed, {len(failed)} failed")
        for result in failed:
            print(f"FAILED [{result['section']}] {result['name']}: {result['actual']} | {result['db']}")
        print(f"Report: {self.REPORT_FILE}")
        return 1 if failed else 0

    # --- sections ------------------------------------------------------------------

    def _verify_meta(self) -> None:
        section = "Meta endpoints"
        self._expect(section, "Health check reports database ok", "GET", "/health", 200,
                     check=lambda body: (body["data"] == {"status": "ok", "database": "ok"}, ""))
        self._expect(section, "Version", "GET", "/version", 200)
        self._expect(section, "Dashboard page is served", "GET", "/", 200, envelope=False)
        self._expect(section, "OpenAPI docs are served", "GET", "/docs", 200, envelope=False)
        self._expect(section, "Unknown route uses the error envelope", "GET", "/no-such-route", 404,
                     check=lambda body: (body["error"]["code"] == "not_found", ""))
        self._expect(section, "Unsupported method uses the error envelope", "PATCH", "/patients", 405,
                     check=lambda body: (body["error"]["code"] == "method_not_allowed", ""))

    def _verify_create(self) -> None:
        section = "POST /patients (valid input)"

        phone = self._phone()
        body = self._expect(section, "Required fields only", "POST", "/patients", 201,
                            body=self._patient(phone_number=phone))
        self._minimal_id = body["data"]["patient_id"]
        self._minimal_phone = phone
        self._record_db(lambda: self._row_matches(
            self._minimal_id,
            first_name="Jordan", last_name="Verify", phone_number=phone, sex="Female",
            state="IL", zip_code="62704", preferred_language="English", email=None,
            address_line_2=None, insurance_provider=None, deleted_at=None,
        ))
        self._record_check(lambda: (
            body["data"]["date_of_birth"] == "04/12/1988"
            and body["data"]["created_at"].endswith("Z")
            and body["data"]["updated_at"] == body["data"]["created_at"]
            and body["data"]["deleted_at"] is None,
            "; date_of_birth returned as MM/DD/YYYY, UTC timestamps, deleted_at null",
        ))

        phone = self._phone()
        body = self._expect(section, "Every optional field supplied", "POST", "/patients", 201,
                            body=self._patient(
                                last_name="Verify-Full", phone_number=phone,
                                email="jordan.verify@example.com", address_line_2="Apt 4B",
                                insurance_provider="Blue Cross", insurance_member_id="ABC123456",
                                preferred_language="Spanish", emergency_contact_name="Sam Verify",
                                emergency_contact_phone="9195559999"))
        self._full_id = body["data"]["patient_id"]
        self._record_db(lambda: self._row_matches(
            self._full_id, email="jordan.verify@example.com", address_line_2="Apt 4B",
            insurance_provider="Blue Cross", insurance_member_id="ABC123456",
            preferred_language="Spanish", emergency_contact_name="Sam Verify",
            emergency_contact_phone="9195559999"))

        phone = self._phone()
        formatted = f"+1 ({phone[:3]}) {phone[3:6]}-{phone[6:]}"
        body = self._expect(section, "Loosely formatted input is normalised", "POST", "/patients", 201,
                            body=self._patient(
                                last_name="Verify-O'Neil", phone_number=formatted, sex="male",
                                state="tx", zip_code="787014321", date_of_birth="1990-03-05",
                                email="MIXED.Case@Example.COM", first_name="  Mary-Jane  "))
        self._normalised_id = body["data"]["patient_id"]
        self._record_db(lambda: self._row_matches(
            self._normalised_id, first_name="Mary-Jane", last_name="Verify-O'Neil",
            phone_number=phone, sex="Male", state="TX", zip_code="78701-4321",
            email="mixed.case@example.com"))

        phone = self._phone()
        hostile = "<script>alert(1)</script>'; DROP TABLE patients;--"
        body = self._expect(section, "HTML and SQL text is stored as plain data", "POST", "/patients", 201,
                            body=self._patient(last_name="Verify-Text", phone_number=phone,
                                               address_line_1=hostile))
        hostile_id = body["data"]["patient_id"]
        self._record_db(lambda: self._row_matches(hostile_id, address_line_1=hostile))

        phone = self._phone()
        body = self._expect(section, "Control characters are stripped", "POST", "/patients", 201,
                            body=self._patient(last_name="Verify-Clean", phone_number=phone,
                                               city="Spring\u0000field\t\n  City"))
        clean_id = body["data"]["patient_id"]
        self._record_db(lambda: self._row_matches(clean_id, city="Spring field City"))

        phone = self._phone()
        today = datetime.now(timezone.utc).date().strftime("%m/%d/%Y")
        self._expect(section, "Date of birth of today is accepted", "POST", "/patients", 201,
                     body=self._patient(last_name="Verify-Today", phone_number=phone, date_of_birth=today))

    def _verify_create_validation(self) -> None:
        section = "POST /patients (invalid input)"
        before = self._test_row_count()
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=2)).strftime("%m/%d/%Y")
        cases = [
            ("3-digit phone number", {"phone_number": "123"}, "phone_number"),
            ("11-digit phone not starting with 1", {"phone_number": "29195550100"}, "phone_number"),
            ("Phone number with letters only", {"phone_number": "call me"}, "phone_number"),
            ("Date of birth in the future", {"date_of_birth": tomorrow}, "date_of_birth"),
            ("Impossible date (02/30)", {"date_of_birth": "02/30/1990"}, "date_of_birth"),
            ("Date of birth not a date", {"date_of_birth": "yesterday"}, "date_of_birth"),
            ("Date of birth before 1900", {"date_of_birth": "01/01/1850"}, "date_of_birth"),
            ("First name with digits", {"first_name": "J0rdan"}, "first_name"),
            ("Last name with symbols", {"last_name": "Verify@Home"}, "last_name"),
            ("First name longer than 50 characters", {"first_name": "A" * 51}, "first_name"),
            ("Sex outside the allowed values", {"sex": "Unknown"}, "sex"),
            ("State that does not exist", {"state": "ZZ"}, "state"),
            ("4-digit ZIP code", {"zip_code": "1234"}, "zip_code"),
            ("ZIP code with letters", {"zip_code": "ABCDE"}, "zip_code"),
            ("Malformed email", {"email": "not-an-email"}, "email"),
            ("City longer than 100 characters", {"city": "C" * 101}, "city"),
            ("Insurance member ID with symbols", {"insurance_member_id": "AB#12"}, "insurance_member_id"),
            ("Emergency contact phone too short", {"emergency_contact_phone": "555"}, "emergency_contact_phone"),
            ("Required field sent as empty string", {"city": "   "}, "city"),
            ("Required field sent as null", {"address_line_1": None}, "address_line_1"),
            ("Wrong JSON type for a field", {"first_name": 12345}, "first_name"),
            ("Unknown field", {"favourite_colour": "blue"}, "favourite_colour"),
        ]
        for name, overrides, field in cases:
            self._expect(section, name, "POST", "/patients", 422,
                         body=self._patient(**{"phone_number": "9195550000", **overrides}),
                         check=lambda body, field=field: self._names_field(body, field))

        self._expect(section, "Several invalid fields are all reported at once", "POST", "/patients", 422,
                     body=self._patient(phone_number="12", state="ZZ", zip_code="1"),
                     check=lambda body: (
                         {detail["field"] for detail in body["error"]["details"]}
                         == {"phone_number", "state", "zip_code"},
                         "; details name phone_number, state, zip_code"))
        self._expect(section, "Empty object lists every required field", "POST", "/patients", 422, body={},
                     check=lambda body: (
                         {detail["field"] for detail in body["error"]["details"]}
                         == {"first_name", "last_name", "date_of_birth", "sex", "phone_number",
                             "address_line_1", "city", "state", "zip_code"},
                         "; all 9 required fields named"))
        self._expect(section, "Body is a JSON array, not an object", "POST", "/patients", 422, body=[1, 2])
        self._expect(section, "Malformed JSON", "POST", "/patients", 400, raw="{not json",
                     check=lambda body: (body["error"]["code"] == "bad_request", ""))
        self._record_db(lambda: (
            self._test_row_count() == before,
            f"no rows inserted by any invalid request (count stayed {before})"))

    def _verify_read(self) -> None:
        section = "GET /patients/:id"
        self._expect(section, "Existing patient", "GET", f"/patients/{self._minimal_id}", 200,
                     check=lambda body: (body["data"]["patient_id"] == self._minimal_id, ""))
        self._expect(section, "Uppercase UUID is accepted", "GET", f"/patients/{self._minimal_id.upper()}", 200)
        self._expect(section, "Well-formed UUID that does not exist", "GET", f"/patients/{uuid.uuid4()}", 404,
                     check=lambda body: (body["error"]["code"] == "not_found", ""))
        self._expect(section, "ID that is not a UUID", "GET", "/patients/12345", 400,
                     check=lambda body: (body["error"]["code"] == "bad_request", ""))

    def _verify_list(self) -> None:
        section = "GET /patients (list and filters)"
        self._expect(section, "No filters returns active patients", "GET", "/patients", 200,
                     check=lambda body: (
                         isinstance(body["data"], list)
                         and len(body["data"]) == self._active_row_count(),
                         f"; {len(body['data'])} returned"),
                     db=lambda: (True, f"matches {self._active_row_count()} active rows in the table"))
        self._expect(section, "last_name filter, exact match", "GET", "/patients?last_name=Verify", 200,
                     check=lambda body: self._only_ids(body, {self._minimal_id}))
        self._expect(section, "last_name filter is case-insensitive", "GET", "/patients?last_name=vERIFY", 200,
                     check=lambda body: self._only_ids(body, {self._minimal_id}))
        self._expect(section, "last_name with an apostrophe", "GET", "/patients?last_name=Verify-O'Neil", 200,
                     check=lambda body: self._only_ids(body, {self._normalised_id}))
        self._expect(section, "phone_number filter, digits only", "GET",
                     f"/patients?phone_number={self._minimal_phone}", 200,
                     check=lambda body: self._only_ids(body, {self._minimal_id}))
        dashed = f"{self._minimal_phone[:3]}-{self._minimal_phone[3:6]}-{self._minimal_phone[6:]}"
        self._expect(section, "phone_number filter, formatted", "GET", f"/patients?phone_number={dashed}", 200,
                     check=lambda body: self._only_ids(body, {self._minimal_id}))
        self._expect(section, "date_of_birth filter, MM/DD/YYYY", "GET",
                     "/patients?date_of_birth=03/05/1990&last_name=Verify-O'Neil", 200,
                     check=lambda body: self._only_ids(body, {self._normalised_id}))
        self._expect(section, "date_of_birth filter, YYYY-MM-DD", "GET",
                     "/patients?date_of_birth=1990-03-05&last_name=Verify-O'Neil", 200,
                     check=lambda body: self._only_ids(body, {self._normalised_id}))
        self._expect(section, "All three filters combined", "GET",
                     f"/patients?last_name=Verify&date_of_birth=04/12/1988&phone_number={self._minimal_phone}", 200,
                     check=lambda body: self._only_ids(body, {self._minimal_id}))
        self._expect(section, "Filters that match nothing return an empty list", "GET",
                     "/patients?last_name=Nobodyhere", 200,
                     check=lambda body: (body["data"] == [], "; empty list"))
        self._expect(section, "SQL injection attempt in a filter matches nothing", "GET",
                     "/patients?last_name=' OR '1'='1", 200,
                     check=lambda body: (body["data"] == [], "; empty list"),
                     db=lambda: (self._test_row_count() > 0, "patients table intact"))
        self._expect(section, "limit restricts the page size", "GET", "/patients?limit=1", 200,
                     check=lambda body: (len(body["data"]) == 1, "; 1 returned"))
        self._expect(section, "Invalid date_of_birth filter", "GET", "/patients?date_of_birth=soon", 400,
                     check=lambda body: self._names_field(body, "date_of_birth"))
        self._expect(section, "Invalid phone_number filter", "GET", "/patients?phone_number=12", 400,
                     check=lambda body: self._names_field(body, "phone_number"))
        self._expect(section, "limit of zero", "GET", "/patients?limit=0", 400,
                     check=lambda body: self._names_field(body, "limit"))

    def _verify_update(self) -> None:
        section = "PUT /patients/:id"
        path = f"/patients/{self._full_id}"
        before = self._row(self._full_id)

        self._expect(section, "Partial update of one field", "PUT", path, 200, body={"city": "Chicago"},
                     check=lambda body: (body["data"]["city"] == "Chicago", ""),
                     db=lambda: self._row_matches(
                         self._full_id, city="Chicago", first_name=before.first_name,
                         email=before.email, phone_number=before.phone_number))
        self._record_db(lambda: (
            self._row(self._full_id).updated_at > before.updated_at
            and self._row(self._full_id).created_at == before.created_at,
            "updated_at advanced, created_at unchanged"))

        self._expect(section, "Several fields, normalised", "PUT", path, 200,
                     body={"state": "ny", "zip_code": "10001", "phone_number": "(919) 555-0777"},
                     db=lambda: self._row_matches(
                         self._full_id, state="NY", zip_code="10001", phone_number="9195550777"))
        self._expect(section, "Optional field cleared with null", "PUT", path, 200, body={"email": None},
                     db=lambda: self._row_matches(self._full_id, email=None))
        self._expect(section, "Invalid value is rejected", "PUT", path, 422, body={"phone_number": "123"},
                     check=lambda body: self._names_field(body, "phone_number"),
                     db=lambda: self._row_matches(self._full_id, phone_number="9195550777"))
        self._expect(section, "One bad field rejects the whole update", "PUT", path, 422,
                     body={"city": "Boston", "zip_code": "12"},
                     db=lambda: self._row_matches(self._full_id, city="Chicago", zip_code="10001"))
        self._expect(section, "Required field cannot be set to null", "PUT", path, 422, body={"last_name": None},
                     check=lambda body: self._names_field(body, "last_name"),
                     db=lambda: self._row_matches(self._full_id, last_name="Verify-Full"))
        self._expect(section, "Future date of birth", "PUT", path, 422, body={"date_of_birth": "01/01/2999"},
                     check=lambda body: self._names_field(body, "date_of_birth"))
        self._expect(section, "Empty body", "PUT", path, 422, body={})
        self._expect(section, "Unknown field", "PUT", path, 422, body={"nickname": "JV"},
                     check=lambda body: self._names_field(body, "nickname"))
        self._expect(section, "Malformed JSON", "PUT", path, 400, raw="{oops")

        fetched = self._http.get(path).json()["data"]
        fetched["city"] = "Evanston"
        self._expect(section, "Full record from GET sent back with one change", "PUT", path, 200, body=fetched,
                     db=lambda: self._row_matches(self._full_id, city="Evanston"))
        self._expect(section, "Client cannot change patient_id or created_at", "PUT", path, 200,
                     body={"patient_id": str(uuid.uuid4()), "created_at": "2000-01-01T00:00:00Z",
                           "city": "Evanston"},
                     db=lambda: (
                         self._row(self._full_id) is not None
                         and self._row(self._full_id).created_at == before.created_at,
                         "patient_id and created_at unchanged"))
        self._expect(section, "Unknown patient", "PUT", f"/patients/{uuid.uuid4()}", 404, body={"city": "X"})
        self._expect(section, "ID that is not a UUID", "PUT", "/patients/abc", 400, body={"city": "X"})

    def _verify_delete(self) -> None:
        section = "DELETE /patients/:id (soft delete)"
        path = f"/patients/{self._normalised_id}"
        self._expect(section, "Delete an existing patient", "DELETE", path, 200,
                     check=lambda body: (body["data"]["deleted_at"] is not None, "; deleted_at returned"),
                     db=lambda: (
                         self._row(self._normalised_id) is not None
                         and self._row(self._normalised_id).deleted_at is not None,
                         "row still exists with deleted_at set (not hard-deleted)"))
        self._expect(section, "Deleted patient is no longer retrievable", "GET", path, 404)
        self._expect(section, "Deleted patient is excluded from the list", "GET",
                     "/patients?last_name=Verify-O'Neil", 200,
                     check=lambda body: (body["data"] == [], "; empty list"))
        self._expect(section, "Deleted patient cannot be updated", "PUT", path, 404, body={"city": "X"})
        self._expect(section, "Deleting twice", "DELETE", path, 404)
        self._expect(section, "Unknown patient", "DELETE", f"/patients/{uuid.uuid4()}", 404)
        self._expect(section, "ID that is not a UUID", "DELETE", "/patients/abc", 400)
        self._expect(section, "Other patients are unaffected", "GET", f"/patients/{self._minimal_id}", 200)

    def _verify_voice_webhook(self) -> None:
        section = "POST /vapi/webhook (voice agent tools)"
        phone = self._phone()
        fields = self._patient(last_name="Verify-Caller", phone_number=phone)
        call_id = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"

        self._expect(section, "Missing webhook secret", "POST", "/vapi/webhook", 401,
                     body={"message": {}}, headers={})
        self._expect(section, "Wrong webhook secret", "POST", "/vapi/webhook", 401,
                     body={"message": {}}, headers={"X-Vapi-Secret": "wrong"})
        self._tool(section, "Unrelated message type is acknowledged", None, {}, call_id,
                   expect=lambda body: (body == {}, "; empty reply"), message_type="status-update")

        self._tool(section, "check_existing_patient: new caller", "check_existing_patient",
                   {"phone_number": phone}, call_id,
                   expect=lambda result: (result["success"] and not result["found"], "; found=false"))
        self._tool(section, "check_existing_patient: 3-digit number", "check_existing_patient",
                   {"phone_number": "123"}, call_id,
                   expect=lambda result: self._tool_invalid(result, {"phone_number"}))
        self._tool(section, "save_patient: invalid date and phone are both reported", "save_patient",
                   {**fields, "date_of_birth": "02/30/1990", "phone_number": "555"}, call_id,
                   expect=lambda result: self._tool_invalid(result, {"date_of_birth", "phone_number"}),
                   db=lambda: (self._rows_with_phone(phone) == 0, "nothing saved"))
        self._tool(section, "save_patient: required field missing", "save_patient",
                   {key: value for key, value in fields.items() if key != "zip_code"}, call_id,
                   expect=lambda result: self._tool_invalid(result, {"zip_code"}),
                   db=lambda: (self._rows_with_phone(phone) == 0, "nothing saved"))

        saved = self._tool(section, "save_patient: confirmed registration", "save_patient",
                           {**fields, "email": "", "state": "Illinois"}, call_id,
                           expect=lambda result: (result["success"] and result["action"] == "created"
                                                  and result["first_name"] == "Jordan", "; created"))
        caller_id = saved["patient_id"]
        self._record_db(lambda: self._row_matches(
            caller_id, last_name="Verify-Caller", phone_number=phone, state="IL", email=None))
        self._record_db(lambda: (
            self._call_log(call_id) is not None and str(self._call_log(call_id).patient_id) == caller_id,
            "call_logs row links the call to the patient"))

        self._tool(section, "save_patient: retried in the same call does not duplicate", "save_patient",
                   {**fields, "city": "Peoria"}, call_id,
                   expect=lambda result: (result["action"] == "updated"
                                          and result["patient_id"] == caller_id, "; updated same record"),
                   db=lambda: (self._rows_with_phone(phone) == 1
                               and self._row(caller_id).city == "Peoria", "still exactly 1 row; city updated"))
        self._tool(section, "Arguments sent as a JSON string (alternate Vapi format)", "check_existing_patient",
                   {"phone_number": phone}, f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}", as_string=True,
                   expect=lambda result: (
                       result["found"] and result["matches"][0]["patient_id"] == caller_id
                       and set(result["matches"][0]) == {"patient_id", "first_name", "last_name"},
                       "; returning caller recognised, only the name is exposed"))

        second_call = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"
        self._tool(section, "update_patient: returning caller changes address", "update_patient",
                   {"patient_id": caller_id, "address_line_1": "9 Oak Avenue", "zip_code": "61602"}, second_call,
                   expect=lambda result: (result["success"] and result["action"] == "updated", "; updated"),
                   db=lambda: self._row_matches(
                       caller_id, address_line_1="9 Oak Avenue", zip_code="61602", city="Peoria"))
        self._tool(section, "update_patient: invalid value", "update_patient",
                   {"patient_id": caller_id, "zip_code": "12"}, second_call,
                   expect=lambda result: self._tool_invalid(result, {"zip_code"}),
                   db=lambda: self._row_matches(caller_id, zip_code="61602"))
        self._tool(section, "update_patient: record does not exist", "update_patient",
                   {"patient_id": str(uuid.uuid4()), "city": "X"}, second_call,
                   expect=lambda result: (result["error_type"] == "not_found", "; not_found"))
        self._tool(section, "update_patient: malformed patient_id", "update_patient",
                   {"patient_id": "abc", "city": "X"}, second_call,
                   expect=lambda result: (result["error_type"] == "system", "; reported as a failure"))
        self._tool(section, "Unknown tool name", "book_flight", {}, second_call,
                   expect=lambda result: (not result["success"] and result["error_type"] == "system", ""))

        self._end_call(section, "End-of-call report stores transcript and summary", call_id,
                       db=lambda: (
                           self._call_log(call_id).transcript == "AI: Hi. User: Hello."
                           and self._call_log(call_id).summary == "Caller registered."
                           and self._call_log(call_id).ended_reason == "assistant-ended-call"
                           and str(self._call_log(call_id).patient_id) == caller_id,
                           "transcript, summary and reason stored; patient link kept"))
        dropped_call = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"
        self._end_call(section, "Call dropped before confirmation saves no patient", dropped_call,
                       reason="customer-ended-call",
                       db=lambda: (
                           self._call_log(dropped_call) is not None
                           and self._call_log(dropped_call).patient_id is None,
                           "call logged with no patient; patients table unchanged"))
        self._expect(section, "GET /patients/:id/calls lists the linked calls", "GET",
                     f"/patients/{caller_id}/calls", 200,
                     check=lambda body: ({call["call_id"] for call in body["data"]} == {call_id, second_call},
                                         "; 2 calls"))

        deleted_call = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"
        deleted_phone = self._phone()
        deleted_fields = self._patient(last_name="Verify-Deleted", phone_number=deleted_phone)
        first = self._tool(section, "save_patient: first save of a call (setup for the next check)",
                           "save_patient", deleted_fields, deleted_call,
                           expect=lambda result: (result["action"] == "created", "; created"))
        self._http.delete(f"/patients/{first['patient_id']}")
        self._tool(section, "save_patient: retried after the record was deleted registers again",
                   "save_patient", deleted_fields, deleted_call,
                   expect=lambda result: (result["success"] and result["action"] == "created"
                                          and result["patient_id"] != first["patient_id"], "; new record"),
                   db=lambda: (self._rows_with_phone(deleted_phone) == 2
                               and self._row(first["patient_id"]).deleted_at is not None,
                               "old row stays soft-deleted, one new active row"))

    def _verify_boundaries(self) -> None:
        section = "Boundary values"

        def accepted(name: str, expected: dict, **overrides) -> str:
            body = self._expect(section, name, "POST", "/patients", 201,
                                body=self._patient(**{"phone_number": self._phone(), **overrides}))
            patient_id = body["data"]["patient_id"]
            self._record_db(lambda: self._row_matches(patient_id, **expected))
            return patient_id

        def rejected(name: str, field: str, **overrides) -> None:
            self._expect(section, name, "POST", "/patients", 422,
                         body=self._patient(**{"phone_number": "9195550000", **overrides}),
                         check=lambda body: self._names_field(body, field))

        accepted("First name of exactly 50 characters", {"first_name": "A" * 50}, first_name="A" * 50)
        accepted("City of exactly 100 characters", {"city": "C" * 100}, city="C" * 100)
        accepted("Street address of exactly 200 characters", {"address_line_1": "S" * 200},
                 address_line_1="S" * 200)
        rejected("Street address of 201 characters", "address_line_1", address_line_1="S" * 201)
        rejected("Apartment line of 101 characters", "address_line_2", address_line_2="U" * 101)
        rejected("Very large value (1 MB) in one field", "address_line_1", address_line_1="X" * 1_000_000)
        accepted("Leap day in a leap year (02/29/2000)", {}, date_of_birth="02/29/2000")
        rejected("Leap day in a non-leap year (02/29/1999)", "date_of_birth", date_of_birth="02/29/1999")
        rejected("Month 13", "date_of_birth", date_of_birth="13/01/1990")
        accepted("ZIP+4 with hyphen", {"zip_code": "62704-1234"}, zip_code="62704-1234")
        rejected("ZIP+4 with too few digits", "zip_code", zip_code="62704-12")
        accepted("Single-letter first name", {"first_name": "J"}, first_name="J")
        accepted("Accented and apostrophe names", {"first_name": "José", "last_name": "Verify-D'Angelo"},
                 first_name="José", last_name="Verify-D'Angelo")
        rejected("Name of only a hyphen", "first_name", first_name="-")
        rejected("Name with a trailing apostrophe", "first_name", first_name="Jordan'")
        accepted("District of Columbia", {"state": "DC"}, state="DC")
        accepted("U.S. territory (PR)", {"state": "PR"}, state="PR")
        for sex in ("Male", "Female", "Other", "Decline to Answer"):
            accepted(f"Sex value: {sex}", {"sex": sex}, sex=sex)
        accepted("preferred_language null falls back to English", {"preferred_language": "English"},
                 preferred_language=None)
        accepted("Empty strings in optional fields are stored as NULL",
                 {"email": None, "address_line_2": None, "insurance_provider": None},
                 email="", address_line_2="  ", insurance_provider="")
        accepted("Emergency contact phone is normalised", {"emergency_contact_phone": "9195558888"},
                 emergency_contact_phone="1-919-555-8888")

        shared_phone = self._phone()
        self._expect(section, "Two patients may share a phone number (first)", "POST", "/patients", 201,
                     body=self._patient(phone_number=shared_phone, first_name="Alex"))
        self._expect(section, "Two patients may share a phone number (second)", "POST", "/patients", 201,
                     body=self._patient(phone_number=shared_phone, first_name="Robin"),
                     db=lambda: (self._rows_with_phone(shared_phone) == 2, "2 rows share the phone"))
        self._tool(section, "Voice lookup on a shared phone returns both people", "check_existing_patient",
                   {"phone_number": shared_phone}, f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}",
                   expect=lambda result: (
                       {match["first_name"] for match in result["matches"]} == {"Alex", "Robin"},
                       "; 2 matches"))

        first = self._http.get("/patients?last_name=Verify&limit=1&offset=0").json()["data"]
        self._expect(section, "offset pages through results", "GET",
                     "/patients?last_name=Verify&limit=1&offset=1", 200,
                     check=lambda body: (len(body["data"]) == 1
                                         and body["data"][0]["patient_id"] != first[0]["patient_id"],
                                         "; a different row from offset 0"))
        self._expect(section, "offset beyond the last row", "GET", "/patients?offset=100000", 200,
                     check=lambda body: (body["data"] == [], "; empty list"))
        self._expect(section, "Negative offset", "GET", "/patients?offset=-1", 400,
                     check=lambda body: self._names_field(body, "offset"))
        self._expect(section, "limit above the maximum (501)", "GET", "/patients?limit=501", 400,
                     check=lambda body: self._names_field(body, "limit"))
        self._expect(section, "limit that is not a number", "GET", "/patients?limit=abc", 400,
                     check=lambda body: self._names_field(body, "limit"))
        self._expect(section, "Empty filter value is ignored", "GET", "/patients?last_name=", 200)
        self._expect(section, "Unknown query parameter is ignored", "GET", "/patients?colour=blue", 200)

    def _verify_webhook_robustness(self) -> None:
        section = "Webhook robustness (malformed Vapi messages)"
        headers = {"X-Vapi-Secret": self._secret}
        call_id = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"
        phone = self._phone()

        def post(name, expected_status, check, *, body=None, raw=None):
            arguments = {"content": raw, "headers": {**headers, "Content-Type": "application/json"}} \
                if raw is not None else {"json": body, "headers": headers}
            response = self._http.post("/vapi/webhook", **arguments)
            passed = response.status_code == expected_status
            note = ""
            if passed and check:
                passed, note = check(response.json())
            self._record(section, name, "POST /vapi/webhook", str(expected_status),
                         f"{response.status_code}{note}", passed)

        def first_result(body):
            return json.loads(body["results"][0]["result"])

        post("Body without a message", 200, lambda body: (body == {}, "; empty reply"), body={})
        post("message is not an object", 200, lambda body: (body == {}, "; empty reply"),
             body={"message": "hello"})
        post("Body is not JSON", 400, None, raw="not json")
        post("Body is a JSON array", 422, None, body=[1])
        post("tool-calls with an empty list", 200, lambda body: (body == {"results": []}, "; no results"),
             body={"message": {"type": "tool-calls", "toolCallList": []}})
        post("Tool call with no name", 200,
             lambda body: (first_result(body)["error_type"] == "system", "; failure result"),
             body={"message": {"type": "tool-calls", "toolCallList": [{"id": "t"}]}})
        post("Tool arguments are a list, not an object", 200,
             lambda body: (first_result(body)["error_type"] == "validation", "; validation result"),
             body={"message": {"type": "tool-calls", "call": {"id": call_id},
                               "toolCallList": [{"id": "t", "name": "save_patient", "arguments": [1, 2]}]}})
        post("Tool arguments are an unparseable string", 200,
             lambda body: (first_result(body)["error_type"] == "validation", "; validation result"),
             body={"message": {"type": "tool-calls", "call": {"id": call_id},
                               "toolCallList": [{"id": "t", "function": {"name": "save_patient",
                                                                          "arguments": "{broken"}}]}})
        post("Message with no call object", 200,
             lambda body: (first_result(body)["success"] is True, "; lookup still answered"),
             body={"message": {"type": "tool-calls",
                               "toolCallList": [{"id": "t", "name": "check_existing_patient",
                                                 "arguments": {"phone_number": phone}}]}})
        post("Two tool calls in one message get two results", 200,
             lambda body: ([entry["toolCallId"] for entry in body["results"]] == ["a", "b"], "; ids a, b"),
             body={"message": {"type": "tool-calls", "call": {"id": call_id}, "toolCallList": [
                 {"id": "a", "name": "check_existing_patient", "arguments": {"phone_number": phone}},
                 {"id": "b", "name": "check_existing_patient", "arguments": {"phone_number": "12"}}]}})
        post("Extra unknown argument does not block a save", 200,
             lambda body: (first_result(body)["success"] is True, "; saved"),
             body={"message": {"type": "tool-calls", "call": {"id": call_id}, "toolCallList": [
                 {"id": "t", "name": "save_patient",
                  "arguments": {**self._patient(phone_number=phone), "confidence": 0.9,
                                "read_back_confirmed": True}}]}})
        self._record_db(lambda: (self._rows_with_phone(phone) == 1, "1 row saved"))
        unconfirmed_phone = self._phone()
        post("save_patient without read_back_confirmed is refused", 200,
             lambda body: (first_result(body)["error_type"] == "confirmation_required", "; confirmation_required"),
             body=self._tool_message("save_patient", self._patient(phone_number=unconfirmed_phone),
                                     f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}", confirmed=False))
        self._record_db(lambda: (self._rows_with_phone(unconfirmed_phone) == 0, "nothing saved"))
        post("End-of-call report with no call id", 200, lambda body: (body == {}, "; ignored"),
             body={"message": {"type": "end-of-call-report", "endedReason": "x"}})

    def _verify_http_behaviour(self) -> None:
        section = "HTTP behaviour"
        response = self._http.get("/health")
        self._record(section, "Security headers on responses", "GET /health",
                     "nosniff, DENY, referrer policy",
                     ", ".join(f"{name}={response.headers.get(name)}" for name in
                               ("x-content-type-options", "x-frame-options", "referrer-policy")),
                     response.headers.get("x-content-type-options") == "nosniff"
                     and response.headers.get("x-frame-options") == "DENY"
                     and response.headers.get("referrer-policy") == "strict-origin-when-cross-origin")
        response = self._http.options("/patients", headers={
            "Origin": "https://reviewer.example", "Access-Control-Request-Method": "POST"})
        self._record(section, "CORS preflight", "OPTIONS /patients", "200 with allow-origin",
                     f"{response.status_code}; allow-origin={response.headers.get('access-control-allow-origin')}",
                     response.status_code == 200
                     and response.headers.get("access-control-allow-origin") in ("*", "https://reviewer.example"))
        response = self._http.get("/patients")
        self._record(section, "Responses are JSON", "GET /patients", "application/json",
                     str(response.headers.get("content-type")),
                     response.headers.get("content-type", "").startswith("application/json"))
        response = self._http.post("/patients", content=json.dumps(self._patient()),
                                   headers={"Content-Type": "text/plain"})
        self._record(section, "Body sent with the wrong content type", "POST /patients (text/plain)", "422",
                     str(response.status_code),
                     response.status_code == 422 and self._is_envelope(response.json(), 422),
                     "nothing saved under phone 9195550000"
                     if self._rows_with_phone("9195550000") == 0 else "ROW WAS SAVED")
        self._results[-1]["passed"] = self._results[-1]["passed"] and self._rows_with_phone("9195550000") == 0
        openapi = self._http.get("/openapi.json").json()
        documented = {(method.upper(), path) for path, item in openapi["paths"].items() for method in item}
        required = {("GET", "/patients"), ("POST", "/patients"), ("GET", "/patients/{patient_id}"),
                    ("PUT", "/patients/{patient_id}"), ("DELETE", "/patients/{patient_id}")}
        self._record(section, "All five required endpoints are in the OpenAPI schema", "GET /openapi.json",
                     "5 endpoints", f"{len(required & documented)} of 5 present", required <= documented)

    def _verify_concurrency(self) -> None:
        section = "Concurrency"
        phones = [self._phone() for _ in range(20)]
        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(
                lambda phone: self._http.post("/patients", json=self._patient(phone_number=phone)).status_code,
                phones))
        saved = sum(self._rows_with_phone(phone) for phone in phones)
        self._record(section, "20 simultaneous creates", "POST /patients x20", "20 x 201",
                     f"{statuses.count(201)} x 201", statuses.count(201) == 20 and saved == 20,
                     f"{saved} rows, one per request")

        target = self._http.post("/patients", json=self._patient(phone_number=self._phone())).json()["data"]
        cities = [f"City{chr(65 + index)}" for index in range(20)]
        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(
                lambda city: self._http.put(f"/patients/{target['patient_id']}", json={"city": city}).status_code,
                cities))
        final_city = self._row(target["patient_id"]).city
        self._record(section, "20 simultaneous updates of one patient", "PUT /patients/{id} x20", "20 x 200",
                     f"{statuses.count(200)} x 200", statuses.count(200) == 20 and final_city in cities,
                     f"row is consistent (city={final_city!r})")

        call_id = f"{self.CALL_PREFIX}{uuid.uuid4().hex[:12]}"
        phone = self._phone()
        message = self._tool_message("save_patient", self._patient(phone_number=phone), call_id)
        with ThreadPoolExecutor(max_workers=10) as pool:
            statuses = list(pool.map(
                lambda _: self._http.post("/vapi/webhook", json=message,
                                          headers={"X-Vapi-Secret": self._secret}).status_code,
                range(10)))
        rows = self._rows_with_phone(phone)
        self._record(section, "10 simultaneous save_patient retries for one call",
                     "POST /vapi/webhook save_patient x10", "10 x 200, 1 patient",
                     f"{statuses.count(200)} x 200", statuses.count(200) == 10 and rows == 1,
                     f"{rows} patient row (no duplicates)")

        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(lambda _: self._http.get("/patients?limit=50").status_code, range(40)))
        self._record(section, "40 simultaneous list requests", "GET /patients x40", "40 x 200",
                     f"{statuses.count(200)} x 200", statuses.count(200) == 40)

    def _verify_database_constraints(self) -> None:
        """Writes that skip the API entirely, to prove the schema itself refuses bad data."""
        section = "Database constraints (direct insert, bypassing the API)"
        valid = PatientCreate(**self._patient(phone_number=self._phone())).model_dump()
        now = datetime.now(timezone.utc)
        cases = [
            ("sex outside the four allowed values", {"sex": "Robot"}),
            ("phone_number with 9 digits", {"phone_number": "919555010"}),
            ("phone_number longer than 10", {"phone_number": "91955501000"}),
            ("first_name NULL", {"first_name": None}),
            ("first_name empty", {"first_name": ""}),
            ("last_name NULL", {"last_name": None}),
            ("date_of_birth NULL", {"date_of_birth": None}),
            ("address_line_1 empty", {"address_line_1": ""}),
            ("city empty", {"city": ""}),
            ("state with one letter", {"state": "I"}),
            ("state with three letters", {"state": "ILL"}),
            ("zip_code with 4 digits", {"zip_code": "1234"}),
            ("emergency_contact_phone with 3 digits", {"emergency_contact_phone": "555"}),
            ("first_name longer than 50", {"first_name": "A" * 51}),
        ]
        for name, overrides in cases:
            self._record_insert(section, name, Patient(**{**valid, **overrides}, created_at=now, updated_at=now))
        self._record_insert(section, "duplicate patient_id (primary key)",
                            Patient(**valid, patient_id=uuid.UUID(self._minimal_id), created_at=now, updated_at=now))
        self._record_insert(section, "call log pointing at a patient that does not exist (foreign key)",
                            CallLog(call_id=f"{self.CALL_PREFIX}fk", patient_id=uuid.uuid4(),
                                    created_at=now, updated_at=now))

    def _record_insert(self, section: str, name: str, row) -> None:
        try:
            with self._database.session() as session:
                session.add(row)
            outcome, rejected = "INSERT SUCCEEDED", False
        except DBAPIError as error:
            outcome, rejected = f"rejected ({type(error.orig).__name__})", True
        self._record(section, name, "INSERT", "rejected by the database", outcome, rejected)

    def _verify_restart_persistence(self) -> None:
        """Starts a second copy of the server on another port, writes a patient, stops the
        process completely, starts a fresh one, and reads the patient back."""
        section = "Persistence across a server restart"
        port = 8011
        url = f"http://127.0.0.1:{port}"
        process = self._start_server(port)
        try:
            created = httpx.post(f"{url}/patients", json=self._patient(
                last_name="Verify-Restart", phone_number=self._phone()), timeout=20).json()["data"]
        finally:
            process.terminate()
            process.wait(timeout=20)
        try:
            httpx.get(f"{url}/health", timeout=3)
            stopped = False
        except httpx.HTTPError:
            stopped = True
        self._record(section, "Server process stopped after the write", f"GET {url}/health",
                     "connection refused", "connection refused" if stopped else "still answering", stopped)

        process = self._start_server(port)
        try:
            response = httpx.get(f"{url}/patients/{created['patient_id']}", timeout=20)
            same = response.status_code == 200 and response.json()["data"] == created
            self._record(section, "Patient is returned unchanged by the new process",
                         "GET /patients/{id}", "200, identical record",
                         f"{response.status_code}; {'identical' if same else 'DIFFERENT'}", same,
                         self._row_matches(created["patient_id"], last_name="Verify-Restart")[1])
            listed = httpx.get(f"{url}/patients?last_name=Verify-Restart", timeout=20).json()["data"]
            self._record(section, "Patient is found by the list filter after restart",
                         "GET /patients?last_name=Verify-Restart", "1 match", f"{len(listed)} match",
                         len(listed) == 1)
        finally:
            process.terminate()
            process.wait(timeout=20)

    @staticmethod
    def _start_server(port: int) -> subprocess.Popen:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "SEED_DEMO_DATA": "false"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                    return process
            except httpx.HTTPError:
                time.sleep(0.5)
        process.terminate()
        raise RuntimeError(f"Server did not start on port {port}")

    def _verify_migrations(self) -> None:
        """Runs the migrations into a throwaway database created beside the live one."""
        section = "Alembic migrations"
        root = Path(__file__).resolve().parents[1]
        live = make_url(self._container.settings().database_url)
        scratch_name = f"verify_migrations_{uuid.uuid4().hex[:10]}"
        admin = create_engine(live, isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{scratch_name}"'))
        except DBAPIError as error:
            self._record(section, "Create a scratch database for the migration checks", "CREATE DATABASE",
                         "created", f"not possible here ({type(error.orig).__name__})", False)
            return
        scratch = create_engine(live.set(database=scratch_name))
        environment = {**os.environ,
                       "DATABASE_URL": live.set(database=scratch_name).render_as_string(hide_password=False)}

        def alembic(*arguments, env=environment) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, "-m", "alembic", *arguments], cwd=root, env=env,
                                  capture_output=True, text=True)

        def objects() -> tuple[set[str], int]:
            with scratch.connect() as connection:
                tables = set(connection.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())
                functions = connection.execute(text(
                    "SELECT count(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace")).scalar()
            scratch.dispose()
            return tables, functions

        try:
            result = alembic("upgrade", "head")
            tables, functions = objects()
            self._record(section, "upgrade head on an empty database", "alembic upgrade head",
                         "tables and SQL functions created",
                         f"exit {result.returncode}; tables {sorted(tables - {'alembic_version'})}; {functions} functions",
                         result.returncode == 0 and {"patients", "call_logs"} <= tables and functions >= 18)
            result = alembic("downgrade", "base")
            tables, functions = objects()
            self._record(section, "downgrade base removes tables and functions", "alembic downgrade base",
                         "tables and functions dropped",
                         f"exit {result.returncode}; tables {sorted(tables - {'alembic_version'})}; {functions} functions",
                         result.returncode == 0 and not {"patients", "call_logs"} & tables and functions == 0)
            result = alembic("upgrade", "head")
            tables, functions = objects()
            self._record(section, "upgrade head again after a downgrade", "alembic upgrade head",
                         "tables and functions recreated", f"exit {result.returncode}; {functions} functions",
                         result.returncode == 0 and {"patients", "call_logs"} <= tables and functions >= 18)
        finally:
            scratch.dispose()
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}" WITH (FORCE)'))
            admin.dispose()

        result = alembic("check", env=dict(os.environ))
        self._record(section, "Live database matches the models (no pending migration)", "alembic check",
                     "no new operations", f"exit {result.returncode}; {result.stdout.strip().splitlines()[-1:]}",
                     result.returncode == 0)
        result = alembic("current", env=dict(os.environ))
        self._record(section, "Live database is at the latest revision", "alembic current", "0002 (head)",
                     result.stdout.strip() or result.stderr.strip()[-80:], "0002 (head)" in result.stdout)

    def _verify_failure_handling(self) -> None:
        """A database outage cannot be staged on a live server, so these three checks run
        the same application in-process with the database call forced to raise."""
        section = "Failure handling (in-process, database call forced to fail)"
        from app.database.database import Database
        from app.main import app
        from app.repositories.patient_repository import PatientRepository

        client = TestClient(app, raise_server_exceptions=False)
        phone = self._phone()
        failure = RuntimeError("simulated database outage")

        with patch.object(PatientRepository, "add", side_effect=failure):
            response = client.post("/patients", json=self._patient(phone_number=phone))
            body = response.json()
            self._record(section, "REST create when the write fails", "POST /patients", "500",
                         str(response.status_code),
                         response.status_code == 500 and body["data"] is None
                         and body["error"]["code"] == "internal_error"
                         and "simulated" not in json.dumps(body),
                         "error envelope returned; internal details not leaked")

            response = client.post(
                "/vapi/webhook", headers={"X-Vapi-Secret": self._secret},
                json=self._tool_message("save_patient", self._patient(phone_number=phone), "inproc-1"))
            result = json.loads(response.json()["results"][0]["result"])
            self._record(section, "Voice save when the write fails", "POST /vapi/webhook save_patient",
                         "200 + failure result", f"{response.status_code}; error_type={result.get('error_type')}",
                         response.status_code == 200 and result["success"] is False
                         and result["error_type"] == "system",
                         "agent is told nothing was saved, so the caller hears an error, not silence")
        self._record_db(lambda: (self._rows_with_phone(phone) == 0, "no partial row written"))

        with patch.object(Database, "execute_scalar", side_effect=failure):
            response = client.get("/health")
            self._record(section, "Health check when the database is unreachable", "GET /health", "500",
                         str(response.status_code),
                         response.status_code == 500
                         and response.json()["error"]["code"] == "database_unavailable", "-")

    # --- request helpers -----------------------------------------------------------

    def _expect(self, section, name, method, path, status, *, body=None, raw=None, headers=None,
                check=None, db=None, envelope=True):
        request_headers = dict(headers or {})
        arguments = {}
        if raw is not None:
            arguments["content"] = raw
            request_headers["Content-Type"] = "application/json"
        elif body is not None:
            arguments["json"] = body
        response = self._http.request(method, path, headers=request_headers, **arguments)
        try:
            payload = response.json()
        except ValueError:
            payload = None

        passed = response.status_code == status
        actual = str(response.status_code)
        if passed and envelope:
            passed = self._is_envelope(payload, response.status_code)
            if not passed:
                actual += "; envelope malformed"
        if passed and check:
            passed, note = check(payload)
            actual += note
        db_note = "-"
        if db:
            db_passed, db_note = db()
            passed = passed and db_passed
        self._record(section, name, f"{method} {self._shorten(path)}", str(status), actual, passed, db_note)
        return payload

    def _tool(self, section, name, tool, arguments, call_id, *, expect, db=None, as_string=False,
              message_type="tool-calls"):
        message = self._tool_message(tool, arguments, call_id, as_string, message_type)
        response = self._http.post("/vapi/webhook", json=message, headers={"X-Vapi-Secret": self._secret})
        passed = response.status_code == 200
        actual = str(response.status_code)
        result = response.json() if passed else {}
        if passed and message_type == "tool-calls":
            entry = result["results"][0]
            passed = entry["toolCallId"] == "tool-1"
            result = json.loads(entry["result"])
        if passed:
            passed, note = expect(result)
            actual += note
        db_note = "-"
        if db:
            db_passed, db_note = db()
            passed = passed and db_passed
        label = f"POST /vapi/webhook {tool}" if tool else f"POST /vapi/webhook ({message_type})"
        self._record(section, name, label, "200", actual, passed, db_note)
        return result

    def _end_call(self, section, name, call_id, *, db, reason="assistant-ended-call"):
        message = {"message": {
            "type": "end-of-call-report", "endedReason": reason,
            "transcript": "AI: Hi. User: Hello.", "analysis": {"summary": "Caller registered."},
            "call": {"id": call_id, "customer": {"number": "+19195550100"}},
        }}
        response = self._http.post("/vapi/webhook", json=message, headers={"X-Vapi-Secret": self._secret})
        db_passed, db_note = db()
        self._record(section, name, "POST /vapi/webhook (end-of-call-report)", "200",
                     str(response.status_code), response.status_code == 200 and db_passed, db_note)

    @staticmethod
    def _tool_message(tool, arguments, call_id, as_string=False, message_type="tool-calls",
                      confirmed=True) -> dict:
        if confirmed and tool in ("save_patient", "update_patient"):
            arguments = {**arguments, "read_back_confirmed": True}
        if as_string:
            tool_call = {"id": "tool-1", "type": "function",
                         "function": {"name": tool, "arguments": json.dumps(arguments)}}
        else:
            tool_call = {"id": "tool-1", "name": tool, "arguments": arguments}
        return {"message": {
            "type": message_type,
            "call": {"id": call_id, "customer": {"number": "+19195550100"}},
            "toolCallList": [tool_call],
        }}

    def _patient(self, **overrides) -> dict:
        patient = {
            "first_name": "Jordan",
            "last_name": self.MARKER,
            "date_of_birth": "04/12/1988",
            "sex": "Female",
            "phone_number": "9195550000",
            "address_line_1": "123 Main Street",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62704",
        }
        patient.update(overrides)
        return patient

    def _phone(self) -> str:
        self._next_phone += 1
        return str(self._next_phone)

    # --- response checks -----------------------------------------------------------

    @staticmethod
    def _is_envelope(payload, status_code: int) -> bool:
        if not isinstance(payload, dict) or set(payload) != {"data", "error"}:
            return False
        if status_code < 400:
            return payload["error"] is None and payload["data"] is not None
        error = payload["error"]
        return (payload["data"] is None and isinstance(error, dict)
                and {"code", "message", "details"} <= set(error))

    @staticmethod
    def _names_field(body: dict, field: str) -> tuple[bool, str]:
        fields = [detail["field"] for detail in body["error"]["details"]]
        return field in fields, f"; error names `{field}`"

    @staticmethod
    def _only_ids(body: dict, expected: set[str]) -> tuple[bool, str]:
        found = {patient["patient_id"] for patient in body["data"]}
        return found == expected, f"; {len(found)} match"

    @staticmethod
    def _tool_invalid(result: dict, fields: set[str]) -> tuple[bool, str]:
        named = {entry["field"] for entry in result.get("invalid_fields", [])}
        return (result["success"] is False and result["error_type"] == "validation" and named == fields,
                "; validation failure naming " + ", ".join(sorted(fields)))

    # --- database checks -----------------------------------------------------------

    def _row(self, patient_id: str) -> Patient | None:
        with self._database.session() as session:
            return session.get(Patient, uuid.UUID(patient_id))

    def _call_log(self, call_id: str) -> CallLog | None:
        with self._database.session() as session:
            return session.get(CallLog, call_id)

    def _row_matches(self, patient_id: str, **expected) -> tuple[bool, str]:
        row = self._row(patient_id)
        if row is None:
            return False, "row not found"
        wrong = {field: getattr(row, field) for field, value in expected.items()
                 if getattr(row, field) != value}
        if wrong:
            return False, f"mismatch: {wrong}"
        shown = ", ".join(f"{field}={value!r}" for field, value in list(expected.items())[:4])
        more = f" (+{len(expected) - 4} more)" if len(expected) > 4 else ""
        return True, f"row has {shown}{more}"

    def _rows_with_phone(self, phone_number: str) -> int:
        with self._database.session() as session:
            return session.scalar(
                select(func.count()).select_from(Patient).where(Patient.phone_number == phone_number))

    def _test_row_count(self) -> int:
        with self._database.session() as session:
            return session.scalar(
                select(func.count()).select_from(Patient).where(Patient.last_name.like(f"{self.MARKER}%")))

    def _active_row_count(self) -> int:
        with self._database.session() as session:
            return min(100, session.scalar(
                select(func.count()).select_from(Patient).where(Patient.deleted_at.is_(None))))

    def _remove_test_rows(self) -> int:
        with self._database.session() as session:
            session.execute(delete(CallLog).where(CallLog.call_id.like(f"{self.CALL_PREFIX}%")))
            session.execute(delete(CallLog).where(CallLog.call_id.like("inproc-%")))
            removed = session.execute(
                delete(Patient).where(Patient.last_name.like(f"{self.MARKER}%"))).rowcount
        return removed

    # --- recording and report ------------------------------------------------------

    def _record(self, section, name, request, expected, actual, passed, db_note="-") -> None:
        self._results.append({"section": section, "name": name, "request": request,
                              "expected": expected, "actual": actual, "db": db_note, "passed": bool(passed)})

    def _record_db(self, db) -> None:
        """Attach a database check to the most recent result."""
        passed, note = db()
        last = self._results[-1]
        last["db"] = note if last["db"] == "-" else f"{last['db']}; {note}"
        last["passed"] = last["passed"] and passed

    def _record_check(self, check) -> None:
        passed, note = check()
        last = self._results[-1]
        last["actual"] += note
        last["passed"] = last["passed"] and passed

    def _shorten(self, path: str) -> str:
        return self.UUID_PATTERN.sub("{id}", path, re.IGNORECASE) if len(path) < 90 else path[:87] + "..."

    def _write_report(self, removed: int) -> None:
        passed = sum(result["passed"] for result in self._results)
        failed = len(self._results) - passed
        engine_name = self._database.execute_scalar("SELECT version()")
        lines = [
            "# API Verification Report",
            "",
            "Generated by `python -m scripts.verify_live_api`. Each check sends a real HTTP request to the "
            "running server and, where the request should (or should not) change data, reads the row "
            "straight from the database to confirm it.",
            "",
            f"- **Run at:** {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
            f"- **Server:** {self._base_url}",
            f"- **Database:** {str(engine_name).split(',')[0]}",
            f"- **Result:** {passed} of {len(self._results)} checks passed" + (f", **{failed} failed**" if failed else ""),
            f"- **Cleanup:** the {removed} test patients this run created (last name starting "
            f"`{self.MARKER}`) and their call logs were removed afterwards.",
            "",
            "## Summary",
            "",
            "| Area | Checks | Passed | Failed |",
            "|---|---|---|---|",
        ]
        sections = list(dict.fromkeys(result["section"] for result in self._results))
        for section in sections:
            rows = [result for result in self._results if result["section"] == section]
            ok = sum(row["passed"] for row in rows)
            lines.append(f"| {section} | {len(rows)} | {ok} | {len(rows) - ok} |")
        for section in sections:
            lines += ["", f"## {section}", "",
                      "| # | Check | Request | Expected | Actual | Database check | Result |",
                      "|---|---|---|---|---|---|---|"]
            rows = [result for result in self._results if result["section"] == section]
            for number, row in enumerate(rows, start=1):
                lines.append("| {} | {} | `{}` | {} | {} | {} | {} |".format(
                    number, self._cell(row["name"]), self._cell(row["request"]), row["expected"],
                    self._cell(row["actual"]), self._cell(row["db"]), "PASS" if row["passed"] else "**FAIL**"))
        lines += [
            "",
            "## Not covered by this run",
            "",
            "- **A real phone call.** The webhook checks above send the same messages Vapi sends, but "
            "speech recognition, the LLM's conversation and the voice are only exercised by calling the number.",
            "- **The Vapi platform itself**: assistant configuration, phone number routing and call audio.",
            "- **Load beyond a few dozen simultaneous requests**, and behaviour with more than one server "
            "process (the duplicate-save guard is an in-process lock).",
            "- **Authentication on the REST API**: there is none, by design for this assessment, so "
            "anyone with the URL can read and change records.",
            "",
        ]
        self.REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _cell(text: str) -> str:
        return str(text).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a running server against its database.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    raise SystemExit(LiveApiVerifier(parser.parse_args().base_url).run())
