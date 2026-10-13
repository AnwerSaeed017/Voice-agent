"""Shared fixtures.

Unit tests (app/tests/unit) touch no database. Integration and browser tests run against
the PostgreSQL database named by DATABASE_URL. Every row they create is marked (a last
name starting "Pytest", or a call id starting "pytest-") and removed before and after
the run, so existing data is left alone.
"""

import json
import logging
import random
import string
import uuid
from datetime import date

import pytest
from sqlalchemy import delete, select

from app.interfaces.utilities import IClock

MARKER = "Pytest"
CALL_PREFIX = "pytest-"


class FixedClock(IClock):
    """A clock that always reports the same moment, for deterministic unit tests."""

    def __init__(self, now) -> None:
        self._now = now

    def utc_now(self):
        return self._now

    def today(self) -> date:
        return self._now.date()


def remove_test_rows(container) -> None:
    from app.models import CallLog, Patient

    marked = select(Patient.patient_id).where(Patient.last_name.like(f"{MARKER}%"))
    with container.database().session() as session:
        session.execute(delete(CallLog).where(CallLog.call_id.like(f"{CALL_PREFIX}%")))
        session.execute(delete(CallLog).where(CallLog.patient_id.in_(marked)))
        session.execute(delete(Patient).where(Patient.last_name.like(f"{MARKER}%")))


@pytest.fixture(scope="session")
def application():
    from app.main import app

    logging.disable(logging.CRITICAL)
    return app


@pytest.fixture(scope="session")
def container(application):
    return application.state.container


@pytest.fixture(scope="session")
def clean_database(container):
    remove_test_rows(container)
    yield
    remove_test_rows(container)


@pytest.fixture(scope="session")
def client(application, clean_database):
    from fastapi.testclient import TestClient

    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def patient_fields():
    """Factory for a valid, unique patient payload. Keyword arguments override fields."""

    def build(**overrides) -> dict:
        suffix = "".join(random.choices(string.ascii_lowercase, k=8))
        fields = {
            "first_name": "Jordan",
            "last_name": MARKER + suffix,
            "date_of_birth": "04/12/1988",
            "sex": "Female",
            "phone_number": "919" + "".join(random.choices(string.digits, k=7)),
            "address_line_1": "123 Main Street",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62704",
        }
        fields.update(overrides)
        return fields

    return build


@pytest.fixture
def create_patient(client, patient_fields):
    def create(**overrides) -> dict:
        response = client.post("/patients", json=patient_fields(**overrides))
        assert response.status_code == 201, response.text
        return response.json()["data"]

    return create


@pytest.fixture
def call_id() -> str:
    return CALL_PREFIX + uuid.uuid4().hex[:12]


@pytest.fixture
def webhook(client, container):
    """Posts a Vapi server message with the shared secret and returns the response."""
    headers = {"X-Vapi-Secret": container.settings().vapi_webhook_secret}

    def post(message: dict):
        return client.post("/vapi/webhook", json={"message": message}, headers=headers)

    return post


@pytest.fixture
def call_tool(webhook):
    """Calls one agent tool the way Vapi does and returns the decoded tool result."""

    def call(name: str, arguments: dict, call_id: str, caller: str = "+19195550100") -> dict:
        response = webhook({
            "type": "tool-calls",
            "call": {"id": call_id, "customer": {"number": caller}},
            "toolCallList": [{"id": "tool-1", "name": name, "arguments": arguments}],
        })
        assert response.status_code == 200, response.text
        entry = response.json()["results"][0]
        assert entry["toolCallId"] == "tool-1"
        return json.loads(entry["result"])

    return call


@pytest.fixture
def end_call(webhook):
    def end(call_id: str, reason: str = "assistant-said-end-call-phrase", transcript: str = "AI: Hi.\nUser: Hello."):
        response = webhook({
            "type": "end-of-call-report",
            "endedReason": reason,
            "transcript": transcript,
            "analysis": {"summary": "Test call."},
            "call": {"id": call_id, "customer": {"number": "+19195550100"}},
        })
        assert response.status_code == 200, response.text

    return end
