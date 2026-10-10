"""Request and response payloads for patients.

Validation lives here (not in the routers or the voice agent) so the REST API and the
phone agent enforce exactly the same rules.
"""

import uuid
from datetime import date, datetime, timezone
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.interfaces.utilities import IFieldNormalizer
from app.utilities.clock import UtcClock
from app.utilities.field_normalizer import FieldNormalizer


class PatientFieldRules(BaseModel):
    """Normalisation shared by every patient payload. Subclasses declare the fields."""

    model_config = ConfigDict(extra="forbid")

    normalizer: ClassVar[IFieldNormalizer] = FieldNormalizer(UtcClock())
    # Set by the server, never by the client. They are dropped from input (rather than
    # rejected as unknown) so a record fetched with GET can be edited and sent back with PUT.
    SERVER_MANAGED_FIELDS: ClassVar[tuple[str, ...]] = (
        "patient_id",
        "created_at",
        "updated_at",
        "deleted_at",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_server_managed_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            return {
                field: value
                for field, value in data.items()
                if field not in cls.SERVER_MANAGED_FIELDS
            }
        return data

    @field_validator("*", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> object:
        return cls.normalizer.clean_text(value)

    @field_validator("first_name", "last_name", mode="before", check_fields=False)
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return cls.normalizer.name(value)

    @field_validator("date_of_birth", mode="before", check_fields=False)
    @classmethod
    def _normalize_date_of_birth(cls, value: object) -> object:
        return cls.normalizer.date_of_birth(value)

    @field_validator("sex", mode="before", check_fields=False)
    @classmethod
    def _normalize_sex(cls, value: object) -> object:
        return cls.normalizer.sex(value)

    @field_validator("phone_number", "emergency_contact_phone", mode="before", check_fields=False)
    @classmethod
    def _normalize_phone(cls, value: object) -> object:
        return cls.normalizer.phone(value)

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return cls.normalizer.email(value)

    @field_validator("state", mode="before", check_fields=False)
    @classmethod
    def _normalize_state(cls, value: object) -> object:
        return cls.normalizer.state(value)

    @field_validator("zip_code", mode="before", check_fields=False)
    @classmethod
    def _normalize_zip_code(cls, value: object) -> object:
        return cls.normalizer.zip_code(value)

    @field_validator("insurance_member_id", mode="before", check_fields=False)
    @classmethod
    def _normalize_member_id(cls, value: object) -> object:
        return cls.normalizer.member_id(value)

    @field_validator("preferred_language", mode="before", check_fields=False)
    @classmethod
    def _default_language(cls, value: object) -> object:
        return cls.normalizer.clean_text(value) or "English"


class PatientCreate(PatientFieldRules):
    """Body of POST /patients, and the arguments of the agent's save_patient tool."""

    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: str | None = None
    address_line_1: str = Field(max_length=200)
    address_line_2: str | None = Field(default=None, max_length=100)
    city: str = Field(max_length=100)
    state: str
    zip_code: str
    insurance_provider: str | None = Field(default=None, max_length=100)
    insurance_member_id: str | None = None
    preferred_language: str = Field(default="English", max_length=50)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = None


class PatientUpdate(PatientFieldRules):
    """Body of PUT /patients/:id. Every field is optional; only those sent are changed."""

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    phone_number: str | None = None
    email: str | None = None
    address_line_1: str | None = Field(default=None, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = Field(default=None, max_length=100)
    insurance_member_id: str | None = None
    preferred_language: str | None = Field(default=None, max_length=50)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = None

    @field_validator(
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone_number",
        "address_line_1",
        "city",
        "state",
        "zip_code",
    )
    @classmethod
    def _required_fields_cannot_be_cleared(cls, value: object) -> object:
        # Optional fields may be set to null to clear them; required ones may not.
        if value is None:
            raise ValueError("is required and cannot be empty")
        return value

    def changes(self) -> dict:
        return self.model_dump(exclude_unset=True)


class PatientFilters(PatientFieldRules):
    """Query parameters of GET /patients."""

    last_name: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    phone_number: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    @field_validator("last_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        # A search term only needs cleaning, not the full name rules.
        return cls.normalizer.clean_text(value)


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: str | None
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    zip_code: str
    insurance_provider: str | None
    insurance_member_id: str | None
    preferred_language: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @field_serializer("date_of_birth")
    def _serialize_date_of_birth(self, value: date) -> str:
        return value.strftime("%m/%d/%Y")

    @field_serializer("created_at", "updated_at", "deleted_at")
    def _serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        # SQLite returns naive datetimes; everything is stored in UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def serialize(cls, patient: object) -> dict:
        return cls.model_validate(patient).model_dump(mode="json")
