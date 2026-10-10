-- Reference DDL (PostgreSQL) for the schema that `alembic upgrade head` creates.
-- Alembic is the source of truth; this file exists so the schema can be read at a glance.

CREATE TABLE patients (
    patient_id               UUID          PRIMARY KEY,
    first_name               VARCHAR(50)   NOT NULL CHECK (length(first_name) >= 1),
    last_name                VARCHAR(50)   NOT NULL CHECK (length(last_name) >= 1),
    date_of_birth            DATE          NOT NULL,
    sex                      VARCHAR(20)   NOT NULL
                             CHECK (sex IN ('Male', 'Female', 'Other', 'Decline to Answer')),
    phone_number             VARCHAR(10)   NOT NULL CHECK (length(phone_number) = 10),
    email                    VARCHAR(254),
    address_line_1           VARCHAR(200)  NOT NULL CHECK (length(address_line_1) >= 1),
    address_line_2           VARCHAR(100),
    city                     VARCHAR(100)  NOT NULL CHECK (length(city) >= 1),
    state                    VARCHAR(2)    NOT NULL CHECK (length(state) = 2),
    zip_code                 VARCHAR(10)   NOT NULL CHECK (length(zip_code) IN (5, 10)),
    insurance_provider       VARCHAR(100),
    insurance_member_id      VARCHAR(50),
    preferred_language       VARCHAR(50)   NOT NULL DEFAULT 'English',
    emergency_contact_name   VARCHAR(100),
    emergency_contact_phone  VARCHAR(10)
                             CHECK (emergency_contact_phone IS NULL
                                    OR length(emergency_contact_phone) = 10),
    created_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    deleted_at               TIMESTAMPTZ   -- soft delete marker (DELETE /patients/:id)
);

CREATE INDEX ix_patients_last_name     ON patients (last_name);
CREATE INDEX ix_patients_date_of_birth ON patients (date_of_birth);
CREATE INDEX ix_patients_phone_number  ON patients (phone_number);

-- Bonus: one row per phone call, linked to the patient it registered (if any).
CREATE TABLE call_logs (
    call_id            VARCHAR(64)  PRIMARY KEY,
    patient_id         UUID         REFERENCES patients (patient_id),
    caller_number      VARCHAR(20),
    ended_reason       VARCHAR(100),
    summary            TEXT,
    transcript         TEXT,
    collected_payload  JSON,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_call_logs_patient_id ON call_logs (patient_id);
