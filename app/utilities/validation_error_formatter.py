from collections.abc import Sequence

from app.interfaces.utilities import IValidationErrorFormatter


class ValidationErrorFormatter(IValidationErrorFormatter):
    """Flattens Pydantic errors into [{"field", "message"}] for API clients and the agent."""

    _LOCATION_PREFIXES = {"body", "query", "path", "header"}
    _REQUIRED_TYPES = {"missing", "string_type", "date_type"}
    _VALUE_ERROR_PREFIX = "Value error, "

    def format(self, errors: Sequence[dict]) -> list[dict]:
        return [
            {"field": self._field(error), "message": self._message(error)} for error in errors
        ]

    def _field(self, error: dict) -> str:
        parts = [
            str(part) for part in error.get("loc", ()) if part not in self._LOCATION_PREFIXES
        ]
        return ".".join(parts) or "body"

    def _message(self, error: dict) -> str:
        error_type = error.get("type", "")
        if error_type in self._REQUIRED_TYPES and error.get("input") is None:
            return "This field is required and cannot be empty."
        if error_type == "missing":
            return "This field is required."
        if error_type == "extra_forbidden":
            return "Unknown field."
        message = str(error.get("msg", "Invalid value."))
        if message.startswith(self._VALUE_ERROR_PREFIX):
            message = message[len(self._VALUE_ERROR_PREFIX):]
        return message[:1].upper() + message[1:]
