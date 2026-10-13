import json
import uuid

from app.constants.constants import UPSERT_FIELDS
from app.interfaces.repository import ICallLogRepository
from app.interfaces.utilities import IClock, IDatabase
from app.models import CallLog
from app.schemas.dashboard import CallListQuery, Page


class CallLogRepository(ICallLogRepository):
    """Persistence for call logs. Every operation is a SQL function defined in
    app/sql/functions/call_logs.sql; no SQL is written here."""

    def __init__(self, database: IDatabase, clock: IClock) -> None:
        self._database = database
        self._clock = clock

    def get(self, call_id: str) -> CallLog | None:
        rows = self._database.call("call_log_get", p_call_id=call_id)
        return CallLog(**rows[0]) if rows else None

    def upsert(self, call_id: str, values: dict) -> CallLog:
        # A field left as None is never written over a value already recorded.
        arguments = {f"p_{field}": values.get(field) for field in UPSERT_FIELDS}
        if arguments["p_collected_payload"] is not None:
            arguments["p_collected_payload"] = json.dumps(arguments["p_collected_payload"], default=str)
        rows = self._database.call(
            "call_log_upsert", p_call_id=call_id, p_now=self._clock.utc_now(), **arguments
        )
        return CallLog(**rows[0])

    def list_for_patient(self, patient_id: uuid.UUID) -> list[CallLog]:
        rows = self._database.call("call_log_list_for_patient", p_patient_id=patient_id)
        return [CallLog(**row) for row in rows]

    def search_page(self, query: CallListQuery) -> Page:
        rows = self._database.call(
            "call_log_search_page",
            p_q=query.q,
            p_outcome=query.outcome,
            p_limit=query.limit,
            p_offset=query.offset,
        )
        items = []
        for row in rows:
            fields = dict(row)
            patient_name = fields.pop("patient_name")
            fields.pop("total_count")
            items.append((CallLog(**fields), patient_name))
        return Page(items, int(rows[0]["total_count"]) if rows else 0)

    def outcome_counts(self) -> dict[str, int]:
        row = self._database.call("call_log_outcome_counts")[0]
        return {name: int(value) for name, value in row.items()}
