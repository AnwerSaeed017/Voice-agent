"""Patient table. Mirrors alembic/versions/0001 and app/sql/schema_reference.sql."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "sex IN ('Male', 'Female', 'Other', 'Decline to Answer')", name="ck_patients_sex"
        ),
        CheckConstraint("length(first_name) >= 1", name="ck_patients_first_name_not_empty"),
        CheckConstraint("length(last_name) >= 1", name="ck_patients_last_name_not_empty"),
        CheckConstraint("length(phone_number) = 10", name="ck_patients_phone_number_length"),
        CheckConstraint("length(address_line_1) >= 1", name="ck_patients_address_line_1_not_empty"),
        CheckConstraint("length(city) >= 1", name="ck_patients_city_not_empty"),
        CheckConstraint("length(state) = 2", name="ck_patients_state_length"),
        CheckConstraint("length(zip_code) IN (5, 10)", name="ck_patients_zip_code_length"),
        CheckConstraint(
            "emergency_contact_phone IS NULL OR length(emergency_contact_phone) = 10",
            name="ck_patients_emergency_contact_phone_length",
        ),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, index=True)
    sex: Mapped[str] = mapped_column(String(20))
    # Digits only, no formatting. Not unique: family members often share a phone.
    phone_number: Mapped[str] = mapped_column(String(10), index=True)
    email: Mapped[str | None] = mapped_column(String(254))

    address_line_1: Mapped[str] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))

    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_id: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(String(50), server_default="English")
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))

    # Timestamps are stored in UTC; the repository sets them from the injected clock.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Soft delete: a non-null value hides the row from every read path.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
