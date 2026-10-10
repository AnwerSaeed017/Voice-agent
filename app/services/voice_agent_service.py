"""Server side of the voice agent: executes the tools the LLM calls during a phone call.

Every tool returns a small JSON object the LLM reads. Failures are always reported back
as data (never as an HTTP error) so the agent can tell the caller what happened instead
of going silent.
"""

import json
import logging
import threading
import uuid

from pydantic import ValidationError

from app.core.exceptions import DomainError, NotFoundError
from app.interfaces.service import ICallLogService, IPatientService, IVoiceAgentService
from app.interfaces.utilities import IFieldNormalizer, IValidationErrorFormatter
from app.schemas.patient import PatientCreate, PatientUpdate


class VoiceAgentService(IVoiceAgentService):
    _logger = logging.getLogger(__name__)
    _save_lock = threading.Lock()

    def __init__(
        self,
        patients: IPatientService,
        call_logs: ICallLogService,
        normalizer: IFieldNormalizer,
        error_formatter: IValidationErrorFormatter,
    ) -> None:
        self._patients = patients
        self._call_logs = call_logs
        self._normalizer = normalizer
        self._error_formatter = error_formatter
        self._tools = {
            "check_existing_patient": self._check_existing_patient,
            "save_patient": self._save_patient,
            "update_patient": self._update_patient,
        }

    def handle_message(self, message: dict) -> dict:
        message_type = message.get("type")
        if message_type == "tool-calls":
            return {"results": self._run_tool_calls(message)}
        if message_type == "end-of-call-report":
            self._record_call_end(message)
        return {}

    # --- tool dispatch -------------------------------------------------------------

    def _run_tool_calls(self, message: dict) -> list[dict]:
        call = message.get("call") or {}
        results = []
        for tool_call in message.get("toolCallList") or message.get("toolCalls") or []:
            name, arguments = self._parse_tool_call(tool_call)
            result = self._run_tool(name, arguments, call)
            self._logger.info(
                "tool_result call_id=%s tool=%s result=%s", call.get("id"), name, json.dumps(result)
            )
            # Vapi expects each result as a single-line string keyed by the tool call id.
            results.append({"toolCallId": tool_call.get("id"), "result": json.dumps(result)})
        return results

    def _run_tool(self, name: str | None, arguments: dict, call: dict) -> dict:
        handler = self._tools.get(name or "")
        if handler is None:
            return self._system_failure(f"Unknown tool '{name}'.")
        try:
            return handler(arguments, call)
        except ValidationError as error:
            return self._validation_failure(self._error_formatter.format(error.errors()))
        except NotFoundError:
            return {
                "success": False,
                "error_type": "not_found",
                "instruction": "That record no longer exists. Offer to register the caller as a new patient.",
            }
        except DomainError as error:
            return self._validation_failure(error.details or [{"field": "body", "message": error.message}])
        except Exception:
            # Database down, constraint violation, bug: the caller must still hear something.
            self._logger.exception("tool_failed call_id=%s tool=%s", call.get("id"), name)
            return self._system_failure("The record could not be saved because of a system error.")

    @staticmethod
    def _parse_tool_call(tool_call: dict) -> tuple[str | None, dict]:
        # Vapi has sent both {"name", "arguments"} and {"function": {"name", "arguments"}}.
        function = tool_call.get("function") or {}
        name = tool_call.get("name") or function.get("name")
        arguments = tool_call.get("arguments", function.get("arguments")) or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        return name, arguments if isinstance(arguments, dict) else {}

    # --- tools ---------------------------------------------------------------------

    def _check_existing_patient(self, arguments: dict, call: dict) -> dict:
        try:
            phone_number = self._normalizer.phone(arguments.get("phone_number"))
        except ValueError as error:
            return self._validation_failure([{"field": "phone_number", "message": str(error)}])
        if phone_number is None:
            return self._validation_failure(
                [{"field": "phone_number", "message": "A phone number is required."}]
            )
        matches = self._patients.find_by_phone(phone_number)
        # Only names are returned: the agent must never read a stored address or date of
        # birth to whoever happens to know a phone number.
        return {
            "success": True,
            "found": bool(matches),
            "matches": [
                {
                    "patient_id": str(patient.patient_id),
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                }
                for patient in matches[:5]
            ],
        }

    def _save_patient(self, arguments: dict, call: dict) -> dict:
        call_id = call.get("id")
        fields = self._patient_fields(arguments)
        # Observability: the final collected payload for every registration attempt.
        self._logger.info("save_patient call_id=%s payload=%s", call_id, json.dumps(fields))

        payload = PatientCreate(**fields)
        if arguments.get("read_back_confirmed") is not True:
            return self._confirmation_required()
        # If the LLM retries after a slow response, update the record this call already
        # created instead of inserting a duplicate. The lock makes "look up, then create"
        # atomic when two retries arrive at the same moment (single server process).
        with self._save_lock:
            existing_patient_id = self._call_logs.registered_patient_id(call_id)
            if existing_patient_id:
                patient = self._patients.update_patient(
                    existing_patient_id, PatientUpdate(**fields)
                )
                action = "updated"
            else:
                patient = self._patients.create_patient(payload)
                action = "created"
            self._link_call(call, patient.patient_id, fields)

        return {
            "success": True,
            "action": action,
            "patient_id": str(patient.patient_id),
            "first_name": patient.first_name,
        }

    def _update_patient(self, arguments: dict, call: dict) -> dict:
        fields = self._patient_fields(arguments)
        self._logger.info(
            "update_patient call_id=%s patient_id=%s payload=%s",
            call.get("id"),
            arguments.get("patient_id"),
            json.dumps(fields),
        )
        try:
            patient_id = uuid.UUID(str(arguments.get("patient_id")))
        except ValueError:
            return self._system_failure("The patient_id was not a valid id from check_existing_patient.")

        changes = PatientUpdate(**fields)
        if arguments.get("read_back_confirmed") is not True:
            return self._confirmation_required()
        patient = self._patients.update_patient(patient_id, changes)
        self._link_call(call, patient.patient_id, fields)
        return {
            "success": True,
            "action": "updated",
            "patient_id": str(patient.patient_id),
            "first_name": patient.first_name,
        }

    # --- helpers -------------------------------------------------------------------

    @staticmethod
    def _patient_fields(arguments: dict) -> dict:
        """Keep only real patient fields, so a stray argument cannot fail the whole save."""
        return {
            field: value
            for field, value in arguments.items()
            if field in PatientCreate.model_fields
        }

    def _link_call(self, call: dict, patient_id: uuid.UUID, fields: dict) -> None:
        try:
            self._call_logs.record_registration(
                call.get("id"), patient_id, self._caller_number(call), fields
            )
        except Exception:
            # The patient is already saved; a logging failure must not be reported as one.
            self._logger.exception("call_log_failed call_id=%s", call.get("id"))

    def _record_call_end(self, message: dict) -> None:
        call = message.get("call") or {}
        artifact = message.get("artifact") or {}
        analysis = message.get("analysis") or {}
        call_id = call.get("id")
        ended_reason = message.get("endedReason")
        try:
            call_log = self._call_logs.record_call_end(
                call_id,
                self._caller_number(call),
                ended_reason,
                message.get("summary") or analysis.get("summary"),
                message.get("transcript") or artifact.get("transcript"),
            )
        except Exception:
            self._logger.exception("call_end_failed call_id=%s", call_id)
            return
        # A call that ends with registered=False dropped (or was abandoned) before the
        # caller confirmed; nothing was saved, by design.
        self._logger.info(
            "call_ended call_id=%s reason=%s registered=%s",
            call_id,
            ended_reason,
            bool(call_log and call_log.patient_id),
        )

    @staticmethod
    def _caller_number(call: dict) -> str | None:
        return (call.get("customer") or {}).get("number")

    @staticmethod
    def _validation_failure(invalid_fields: list[dict]) -> dict:
        return {
            "success": False,
            "error_type": "validation",
            "invalid_fields": invalid_fields,
            "instruction": (
                "Nothing was saved. Ask the caller again for only these fields, explaining "
                "the problem in plain words, then call the tool again with every field."
            ),
        }

    @staticmethod
    def _confirmation_required() -> dict:
        """Server-side guard for the brief's rule that nothing is saved before the caller
        has heard everything read back and confirmed it."""
        return {
            "success": False,
            "error_type": "confirmation_required",
            "instruction": (
                "Nothing was saved. Read every collected detail back to the caller in full, "
                "ask if it is all correct, and only after a clear yes call the tool again "
                "with read_back_confirmed set to true."
            ),
        }

    @staticmethod
    def _system_failure(reason: str) -> dict:
        return {
            "success": False,
            "error_type": "system",
            "reason": reason,
            "instruction": (
                "Nothing was saved. Apologise, say there is a technical problem on our side, "
                "and try the tool once more. If it fails again, tell the caller the "
                "registration could not be completed and to call back later, then end the call."
            ),
        }
