"""REST API for patient records. HTTP concerns only; rules live in PatientService."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.containers.container import Container
from app.interfaces.service import ICallLogService, IPatientService
from app.interfaces.utilities import IRequestParser, IResponseBuilder
from app.schemas.call_log import CallLogResponse
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate

patient_router = APIRouter(prefix="/patients", tags=["Patients"])


@patient_router.get(
    "",
    summary="List patients",
    description="List all patients, optionally filtered by last name, date of birth or phone number.",
)
@inject
def list_patients(
    last_name: str | None = Query(None, description="Exact match, case-insensitive"),
    date_of_birth: str | None = Query(None, description="MM/DD/YYYY or YYYY-MM-DD"),
    phone_number: str | None = Query(None, description="10 digits, any formatting"),
    limit: str | None = Query(None, description="1-500, default 100"),
    offset: str | None = Query(None, description="Default 0"),
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    parser: IRequestParser = Depends(Provide[Container.utilities.request_parser]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    filters = parser.patient_filters(
        {
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "phone_number": phone_number,
            "limit": limit,
            "offset": offset,
        }
    )
    found = patients.list_patients(filters)
    return responses.success([PatientResponse.serialize(patient) for patient in found])


@patient_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a patient",
    description="Create a new patient. Returns the created record with its patient_id.",
)
@inject
def create_patient(
    payload: PatientCreate,
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    patient = patients.create_patient(payload)
    return responses.success(PatientResponse.serialize(patient), status.HTTP_201_CREATED)


@patient_router.get(
    "/{patient_id}",
    summary="Get a patient",
    description="Retrieve a single patient by patient_id (UUID).",
)
@inject
def get_patient(
    patient_id: str,
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    parser: IRequestParser = Depends(Provide[Container.utilities.request_parser]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    patient = patients.get_patient(parser.patient_id(patient_id))
    return responses.success(PatientResponse.serialize(patient))


@patient_router.put(
    "/{patient_id}",
    summary="Update a patient",
    description="Update an existing patient. Partial updates are allowed: only the fields sent are changed.",
)
@inject
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    parser: IRequestParser = Depends(Provide[Container.utilities.request_parser]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    patient = patients.update_patient(parser.patient_id(patient_id), payload)
    return responses.success(PatientResponse.serialize(patient))


@patient_router.delete(
    "/{patient_id}",
    summary="Soft-delete a patient",
    description="Sets deleted_at on the record. The row is kept but no longer returned by the API.",
)
@inject
def delete_patient(
    patient_id: str,
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    parser: IRequestParser = Depends(Provide[Container.utilities.request_parser]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    patient = patients.delete_patient(parser.patient_id(patient_id))
    return responses.success(PatientResponse.serialize(patient))


@patient_router.get(
    "/{patient_id}/calls",
    summary="List a patient's calls",
    description="Call transcripts and summaries linked to this patient.",
)
@inject
def list_patient_calls(
    patient_id: str,
    patients: IPatientService = Depends(Provide[Container.services.patient_service]),
    call_logs: ICallLogService = Depends(Provide[Container.services.call_log_service]),
    parser: IRequestParser = Depends(Provide[Container.utilities.request_parser]),
    responses: IResponseBuilder = Depends(Provide[Container.utilities.response_builder]),
) -> JSONResponse:
    patient = patients.get_patient(parser.patient_id(patient_id))
    found = call_logs.list_for_patient(patient.patient_id)
    return responses.success([CallLogResponse.serialize(call_log) for call_log in found])
