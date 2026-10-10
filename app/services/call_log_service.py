import uuid

from app.interfaces.repository import ICallLogRepository
from app.interfaces.service import ICallLogService
from app.models import CallLog


class CallLogService(ICallLogService):
    def __init__(self, call_logs: ICallLogRepository) -> None:
        self._call_logs = call_logs

    def registered_patient_id(self, call_id: str | None) -> uuid.UUID | None:
        if not call_id:
            return None
        call_log = self._call_logs.get(call_id)
        return call_log.patient_id if call_log else None

    def record_registration(
        self, call_id: str | None, patient_id: uuid.UUID, caller_number: str | None, payload: dict
    ) -> None:
        if not call_id:
            return
        self._call_logs.upsert(
            call_id,
            {
                "patient_id": patient_id,
                "caller_number": caller_number,
                "collected_payload": payload,
            },
        )

    def record_call_end(
        self,
        call_id: str | None,
        caller_number: str | None,
        ended_reason: str | None,
        summary: str | None,
        transcript: str | None,
    ) -> CallLog | None:
        if not call_id:
            return None
        return self._call_logs.upsert(
            call_id,
            {
                "caller_number": caller_number,
                "ended_reason": ended_reason,
                "summary": summary,
                "transcript": transcript,
            },
        )

    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]:
        return self._call_logs.list_for_patient(patient_id)
