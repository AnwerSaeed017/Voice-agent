"""One row per phone call: what was collected, how the call ended, and the transcript."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    # Vapi's call id. Also what makes save_patient idempotent within a call.
    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Null when the call ended before a registration was confirmed (e.g. the line dropped).
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.patient_id", name="fk_call_logs_patient_id"), index=True
    )
    caller_number: Mapped[str | None] = mapped_column(String(20))
    ended_reason: Mapped[str | None] = mapped_column(String(100))
    summary: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    collected_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
