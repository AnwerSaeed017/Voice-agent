from collections.abc import Sequence

from app.constants.constants import (
    ERROR_LOCATION_PREFIXES,
    REQUIRED_ERROR_TYPES,
    VALUE_ERROR_PREFIX,
)
from app.interfaces.utilities import IValidationErrorFormatter


class ValidationErrorFormatter(IValidationErrorFormatter):
    """Flattens Pydantic errors into [{"field", "message"}] for API clients and the agent."""

    def format(self, errors: Sequence[dict]) -> list[dict]:
        return [
            {"field": self._field(error), "message": self._message(error)} for error in errors
        ]

    def _field(self, error: dict) -> str:
        parts = [
            str(part) for part in error.get("loc", ()) if part not in ERROR_LOCATION_PREFIXES
        ]
        return ".".join(parts) or "body"

    def _message(self, error: dict) -> str:
        error_type = error.get("type", "")
        if error_type in REQUIRED_ERROR_TYPES and error.get("input") is None:
            return "This field is required and cannot be empty."
        if error_type == "missing":
            return "This field is required."
        if error_type == "extra_forbidden":
            return "Unknown field."
        message = str(error.get("msg", "Invalid value."))
        if message.startswith(VALUE_ERROR_PREFIX):
            message = message[len(VALUE_ERROR_PREFIX):]
        return message[:1].upper() + message[1:]
