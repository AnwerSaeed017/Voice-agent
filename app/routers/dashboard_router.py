"""Read endpoints behind the web console: search, paging and headline numbers.

They sit beside the REST API in the brief (/patients), which is left unchanged. The
console still creates nothing here, and edits or deletes patients through /patients.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.containers.container import Container
from app.interfaces.service import IDashboardService
from app.interfaces.utilities import IResponseBuilder
from app.schemas.call_log import CallLogResponse
from app.schemas.dashboard import (
    CallListQuery,
    CallOutcome,
    PatientListQuery,
    PatientSort,
    PatientSource,
)
from app.schemas.patient import PatientResponse

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get(
    "/summary",
    summary="Headline numbers",
    description="Patient and call totals, record completeness, and registrations per day.",
)
@inject
def get_summary(
    days: int = Query(14, ge=7, le=90, description="Days to chart, ending today"),
    utc_offset_minutes: int = Query(0, ge=-840, le=840, description="Viewer's offset from UTC"),
    dashboard: IDashboardService = Depends(Provide[Container.services.dashboard_service]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    return responses.success(dashboard.summary(days, utc_offset_minutes))


@dashboard_router.get(
    "/patients",
    summary="Search patients",
    description="Partial-match search across name, phone, email, city and insurer, with paging.",
)
@inject
def search_patients(
    q: str | None = Query(None, max_length=100),
    source: PatientSource = Query("all", description="How the patient registered"),
    sort: PatientSort = Query("newest"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    dashboard: IDashboardService = Depends(Provide[Container.services.dashboard_service]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    page = dashboard.list_patients(
        PatientListQuery(q=(q or "").strip() or None, source=source, sort=sort, limit=limit, offset=offset)
    )
    items = [
        {**PatientResponse.serialize(patient), "call_count": call_count}
        for patient, call_count in page.items
    ]
    return responses.success({"items": items, "total": page.total})


@dashboard_router.get(
    "/calls",
    summary="Search calls",
    description="Every call the agent handled, including those that ended without a registration.",
)
@inject
def search_calls(
    q: str | None = Query(None, max_length=100, description="Patient name, caller number or transcript text"),
    outcome: CallOutcome = Query("all"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    dashboard: IDashboardService = Depends(Provide[Container.services.dashboard_service]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    page = dashboard.list_calls(
        CallListQuery(q=(q or "").strip() or None, outcome=outcome, limit=limit, offset=offset)
    )
    items = [
        {
            **CallLogResponse.serialize(call_log),
            "registered": call_log.patient_id is not None,
            "patient_name": patient_name,
        }
        for call_log, patient_name in page.items
    ]
    return responses.success({"items": items, "total": page.total})
