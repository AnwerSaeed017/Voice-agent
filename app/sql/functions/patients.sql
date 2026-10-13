-- Patient functions, called by app/repositories/patient_repository.py.
-- Loaded by the Alembic migration that follows the table migrations.
-- Every read hides soft-deleted rows. Text parameters that carry JSON are cast here.

CREATE OR REPLACE FUNCTION patient_add(p_values text, p_now timestamptz)
RETURNS SETOF patients
LANGUAGE sql AS $$
    INSERT INTO patients
    SELECT *
    FROM jsonb_populate_record(
        NULL::patients,
        p_values::jsonb || jsonb_build_object(
            'patient_id', gen_random_uuid(),
            'preferred_language', COALESCE(p_values::jsonb ->> 'preferred_language', 'English'),
            'created_at', p_now,
            'updated_at', p_now,
            'deleted_at', NULL
        )
    )
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION patient_get(p_patient_id uuid)
RETURNS SETOF patients
LANGUAGE sql STABLE AS $$
    SELECT * FROM patients WHERE patient_id = p_patient_id AND deleted_at IS NULL;
$$;

-- Exact-match filters of GET /patients.
CREATE OR REPLACE FUNCTION patient_search(
    p_last_name text, p_date_of_birth date, p_phone_number text, p_limit integer, p_offset integer
)
RETURNS SETOF patients
LANGUAGE sql STABLE AS $$
    SELECT *
    FROM patients
    WHERE deleted_at IS NULL
      AND (p_last_name IS NULL OR lower(last_name) = lower(p_last_name))
      AND (p_date_of_birth IS NULL OR date_of_birth = p_date_of_birth)
      AND (p_phone_number IS NULL OR phone_number = p_phone_number)
    ORDER BY created_at DESC, patient_id
    LIMIT p_limit OFFSET p_offset;
$$;

-- Partial update. p_changes is a JSON object holding only the fields to change;
-- a key present with a null value clears that field, an absent key leaves it alone.
CREATE OR REPLACE FUNCTION patient_update(p_patient_id uuid, p_changes text, p_now timestamptz)
RETURNS SETOF patients
LANGUAGE sql AS $$
    UPDATE patients AS p
    SET first_name = CASE WHEN c -> 'first_name' IS NOT NULL THEN c ->> 'first_name' ELSE p.first_name END,
        last_name = CASE WHEN c -> 'last_name' IS NOT NULL THEN c ->> 'last_name' ELSE p.last_name END,
        date_of_birth = CASE WHEN c -> 'date_of_birth' IS NOT NULL THEN (c ->> 'date_of_birth')::date ELSE p.date_of_birth END,
        sex = CASE WHEN c -> 'sex' IS NOT NULL THEN c ->> 'sex' ELSE p.sex END,
        phone_number = CASE WHEN c -> 'phone_number' IS NOT NULL THEN c ->> 'phone_number' ELSE p.phone_number END,
        email = CASE WHEN c -> 'email' IS NOT NULL THEN c ->> 'email' ELSE p.email END,
        address_line_1 = CASE WHEN c -> 'address_line_1' IS NOT NULL THEN c ->> 'address_line_1' ELSE p.address_line_1 END,
        address_line_2 = CASE WHEN c -> 'address_line_2' IS NOT NULL THEN c ->> 'address_line_2' ELSE p.address_line_2 END,
        city = CASE WHEN c -> 'city' IS NOT NULL THEN c ->> 'city' ELSE p.city END,
        state = CASE WHEN c -> 'state' IS NOT NULL THEN c ->> 'state' ELSE p.state END,
        zip_code = CASE WHEN c -> 'zip_code' IS NOT NULL THEN c ->> 'zip_code' ELSE p.zip_code END,
        insurance_provider = CASE WHEN c -> 'insurance_provider' IS NOT NULL THEN c ->> 'insurance_provider' ELSE p.insurance_provider END,
        insurance_member_id = CASE WHEN c -> 'insurance_member_id' IS NOT NULL THEN c ->> 'insurance_member_id' ELSE p.insurance_member_id END,
        preferred_language = CASE WHEN c -> 'preferred_language' IS NOT NULL THEN c ->> 'preferred_language' ELSE p.preferred_language END,
        emergency_contact_name = CASE WHEN c -> 'emergency_contact_name' IS NOT NULL THEN c ->> 'emergency_contact_name' ELSE p.emergency_contact_name END,
        emergency_contact_phone = CASE WHEN c -> 'emergency_contact_phone' IS NOT NULL THEN c ->> 'emergency_contact_phone' ELSE p.emergency_contact_phone END,
        updated_at = p_now
    FROM (SELECT p_changes::jsonb AS c) AS changes
    WHERE p.patient_id = p_patient_id AND p.deleted_at IS NULL
    RETURNING p.*;
$$;

CREATE OR REPLACE FUNCTION patient_soft_delete(p_patient_id uuid, p_now timestamptz)
RETURNS SETOF patients
LANGUAGE sql AS $$
    UPDATE patients
    SET deleted_at = p_now, updated_at = p_now
    WHERE patient_id = p_patient_id AND deleted_at IS NULL
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION patient_find_by_phone(p_phone_number text)
RETURNS SETOF patients
LANGUAGE sql STABLE AS $$
    SELECT *
    FROM patients
    WHERE deleted_at IS NULL AND phone_number = p_phone_number
    ORDER BY updated_at DESC;
$$;

-- Counts every row, deleted or not: used to decide whether the table has ever held data.
CREATE OR REPLACE FUNCTION patient_count()
RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT count(*) FROM patients;
$$;

-- The console's search predicate, shared by the page and its count.
-- position() is used instead of LIKE so that wildcard characters in p_q match literally.
CREATE OR REPLACE FUNCTION patient_matches(p patients, p_q text, p_source text)
RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT p.deleted_at IS NULL
       AND (p_source = 'all'
            OR (p_source = 'voice') = EXISTS (SELECT 1 FROM call_logs AS c WHERE c.patient_id = p.patient_id))
       AND (p_q IS NULL
            OR position(lower(p_q) IN lower(p.first_name || ' ' || p.last_name)) > 0
            OR position(lower(p_q) IN lower(COALESCE(p.email, ''))) > 0
            OR position(lower(p_q) IN lower(p.city)) > 0
            OR position(lower(p_q) IN lower(COALESCE(p.insurance_provider, ''))) > 0
            OR (length(regexp_replace(p_q, '[^0-9]', '', 'g')) >= 3
                AND position(regexp_replace(p_q, '[^0-9]', '', 'g') IN p.phone_number) > 0));
$$;

CREATE OR REPLACE FUNCTION patient_search_page(
    p_q text, p_source text, p_sort text, p_limit integer, p_offset integer
)
RETURNS SETOF patients
LANGUAGE sql STABLE AS $$
    SELECT p.*
    FROM patients AS p
    WHERE patient_matches(p, p_q, p_source)
    ORDER BY CASE WHEN p_sort = 'newest' THEN p.created_at END DESC,
             CASE WHEN p_sort = 'oldest' THEN p.created_at END ASC,
             CASE WHEN p_sort = 'name' THEN lower(p.last_name) END ASC,
             CASE WHEN p_sort = 'name' THEN lower(p.first_name) END ASC,
             CASE WHEN p_sort = 'name_desc' THEN lower(p.last_name) END DESC,
             CASE WHEN p_sort = 'name_desc' THEN lower(p.first_name) END DESC,
             p.patient_id
    LIMIT p_limit OFFSET p_offset;
$$;

CREATE OR REPLACE FUNCTION patient_search_page_count(p_q text, p_source text)
RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT count(*) FROM patients AS p WHERE patient_matches(p, p_q, p_source);
$$;

-- Number of calls linked to each of the given patients. Patients with no calls are absent.
CREATE OR REPLACE FUNCTION patient_call_counts(p_patient_ids text[])
RETURNS TABLE (patient_id uuid, call_count bigint)
LANGUAGE sql STABLE AS $$
    SELECT c.patient_id, count(*)
    FROM call_logs AS c
    WHERE c.patient_id = ANY (p_patient_ids::uuid[])
    GROUP BY c.patient_id;
$$;

-- count(column) counts the rows where that column is not null.
CREATE OR REPLACE FUNCTION patient_completeness_counts()
RETURNS TABLE (
    total bigint, with_email bigint, with_insurance bigint,
    with_emergency_contact bigint, with_unit bigint, voice bigint
)
LANGUAGE sql STABLE AS $$
    SELECT count(*),
           count(p.email),
           count(p.insurance_provider),
           count(p.emergency_contact_name),
           count(p.address_line_2),
           count(*) FILTER (WHERE EXISTS (SELECT 1 FROM call_logs AS c WHERE c.patient_id = p.patient_id))
    FROM patients AS p
    WHERE p.deleted_at IS NULL;
$$;

CREATE OR REPLACE FUNCTION patient_registration_times(p_since timestamptz)
RETURNS SETOF timestamptz
LANGUAGE sql STABLE AS $$
    SELECT created_at FROM patients WHERE deleted_at IS NULL AND created_at >= p_since;
$$;
