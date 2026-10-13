-- Removes every function created by patients.sql and call_logs.sql (migration downgrade).
-- patient_matches goes after the two functions that call it.

DROP FUNCTION IF EXISTS call_log_outcome_counts;
DROP FUNCTION IF EXISTS call_log_search_page;
DROP FUNCTION IF EXISTS call_log_list_for_patient;
DROP FUNCTION IF EXISTS call_log_upsert;
DROP FUNCTION IF EXISTS call_log_get;
DROP FUNCTION IF EXISTS patient_registration_times;
DROP FUNCTION IF EXISTS patient_completeness_counts;
DROP FUNCTION IF EXISTS patient_call_counts;
DROP FUNCTION IF EXISTS patient_search_page_count;
DROP FUNCTION IF EXISTS patient_search_page;
DROP FUNCTION IF EXISTS patient_matches;
DROP FUNCTION IF EXISTS patient_count;
DROP FUNCTION IF EXISTS patient_find_by_phone;
DROP FUNCTION IF EXISTS patient_soft_delete;
DROP FUNCTION IF EXISTS patient_update;
DROP FUNCTION IF EXISTS patient_search;
DROP FUNCTION IF EXISTS patient_get;
DROP FUNCTION IF EXISTS patient_add;
