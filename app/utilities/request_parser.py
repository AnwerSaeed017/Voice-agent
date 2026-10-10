import uuid

from pydantic import ValidationError

from app.core.exceptions import BadRequestError
from app.interfaces.utilities import IRequestParser, IValidationErrorFormatter
from app.schemas.patient import PatientFilters


class RequestParser(IRequestParser):
    """A malformed id or filter is the client's request being wrong, so both map to 400."""

    def __init__(self, error_formatter: IValidationErrorFormatter) -> None:
        self._error_formatter = error_formatter

    def patient_id(self, raw: str) -> uuid.UUID:
        try:
            return uuid.UUID(raw)
        except ValueError:
            raise BadRequestError(
                "patient_id must be a valid UUID.",
                [{"field": "patient_id", "message": "Not a valid UUID."}],
            ) from None

    def patient_filters(self, raw: dict) -> PatientFilters:
        provided = {name: value for name, value in raw.items() if value is not None}
        try:
            return PatientFilters(**provided)
        except ValidationError as error:
            raise BadRequestError(
                "One or more query parameters are invalid.",
                self._error_formatter.format(error.errors()),
            ) from None
