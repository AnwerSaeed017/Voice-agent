-- Call log functions, called by app/repositories/call_log_repository.py.
-- Loaded by the Alembic migration that follows the table migrations.

CREATE OR REPLACE FUNCTION call_log_get(p_call_id text)
RETURNS SETOF call_logs
LANGUAGE sql STABLE AS $$
    SELECT * FROM call_logs WHERE call_id = p_call_id;
$$;

-- Creates the row for a call, or adds to it. A null argument never overwrites a value
-- already recorded, so the save step and the end-of-call report can arrive in either order.
CREATE OR REPLACE FUNCTION call_log_upsert(
    p_call_id text, p_patient_id uuid, p_caller_number text, p_ended_reason text,
    p_summary text, p_transcript text, p_collected_payload text, p_now timestamptz
)
RETURNS SETOF call_logs
LANGUAGE sql AS $$
    INSERT INTO call_logs AS existing (
        call_id, patient_id, caller_number, ended_reason, summary, transcript,
        collected_payload, created_at, updated_at
    )
    VALUES (
        p_call_id, p_patient_id, p_caller_number, p_ended_reason, p_summary, p_transcript,
        p_collected_payload::json, p_now, p_now
    )
    ON CONFLICT (call_id) DO UPDATE
    SET patient_id = COALESCE(EXCLUDED.patient_id, existing.patient_id),
        caller_number = COALESCE(EXCLUDED.caller_number, existing.caller_number),
        ended_reason = COALESCE(EXCLUDED.ended_reason, existing.ended_reason),
        summary = COALESCE(EXCLUDED.summary, existing.summary),
        transcript = COALESCE(EXCLUDED.transcript, existing.transcript),
        collected_payload = COALESCE(EXCLUDED.collected_payload, existing.collected_payload),
        updated_at = p_now
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION call_log_list_for_patient(p_patient_id uuid)
RETURNS SETOF call_logs
LANGUAGE sql STABLE AS $$
    SELECT * FROM call_logs WHERE patient_id = p_patient_id ORDER BY created_at DESC;
$$;

-- Every call, newest first, with the name of its patient when that patient is still active.
-- total_count is the number of calls matching the filters, repeated on each row.
CREATE OR REPLACE FUNCTION call_log_search_page(
    p_q text, p_outcome text, p_limit integer, p_offset integer
)
RETURNS TABLE (
    call_id varchar, patient_id uuid, caller_number varchar, ended_reason varchar,
    summary text, transcript text, created_at timestamptz, updated_at timestamptz,
    patient_name text, total_count bigint
)
LANGUAGE sql STABLE AS $$
    SELECT c.call_id, c.patient_id, c.caller_number, c.ended_reason, c.summary, c.transcript,
           c.created_at, c.updated_at,
           p.first_name || ' ' || p.last_name,
           count(*) OVER ()
    FROM call_logs AS c
    LEFT JOIN patients AS p ON p.patient_id = c.patient_id AND p.deleted_at IS NULL
    WHERE (p_outcome = 'all' OR (p_outcome = 'registered') = (c.patient_id IS NOT NULL))
      AND (p_q IS NULL
           OR position(lower(p_q) IN lower(COALESCE(p.first_name || ' ' || p.last_name, ''))) > 0
           OR position(lower(p_q) IN lower(COALESCE(c.transcript, ''))) > 0
           OR (length(regexp_replace(p_q, '[^0-9]', '', 'g')) >= 3
               AND position(regexp_replace(p_q, '[^0-9]', '', 'g') IN COALESCE(c.caller_number, '')) > 0))
    ORDER BY c.created_at DESC, c.call_id
    LIMIT p_limit OFFSET p_offset;
$$;

CREATE OR REPLACE FUNCTION call_log_outcome_counts()
RETURNS TABLE (total bigint, registered bigint)
LANGUAGE sql STABLE AS $$
    SELECT count(*), count(patient_id) FROM call_logs;
$$;
