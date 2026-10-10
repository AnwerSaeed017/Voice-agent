import uuid

from sqlalchemy import select

from app.interfaces.repository import ICallLogRepository
from app.interfaces.utilities import IClock, IDatabase
from app.models import CallLog


class CallLogRepository(ICallLogRepository):
    def __init__(self, database: IDatabase, clock: IClock) -> None:
        self._database = database
        self._clock = clock

    def get(self, call_id: str) -> CallLog | None:
        with self._database.session() as session:
            return session.get(CallLog, call_id)

    def upsert(self, call_id: str, values: dict) -> CallLog:
        now = self._clock.utc_now()
        with self._database.session() as session:
            call_log = session.get(CallLog, call_id)
            if call_log is None:
                call_log = CallLog(call_id=call_id, created_at=now)
                session.add(call_log)
            for field, value in values.items():
                # Never overwrite something already recorded with "unknown".
                if value is not None:
                    setattr(call_log, field, value)
            call_log.updated_at = now
            return call_log

    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]:
        statement = (
            select(CallLog)
            .where(CallLog.patient_id == patient_id)
            .order_by(CallLog.created_at.desc())
        )
        with self._database.session() as session:
            return list(session.scalars(statement))
