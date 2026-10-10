import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


class CallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_id: str
    patient_id: uuid.UUID | None
    caller_number: str | None
    ended_reason: str | None
    summary: str | None
    transcript: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def serialize(cls, call_log: object) -> dict:
        return cls.model_validate(call_log).model_dump(mode="json")
