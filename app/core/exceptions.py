"""Domain errors. Services raise these; ExceptionHandlers turns them into HTTP responses."""


class DomainError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class BadRequestError(DomainError):
    """The request itself is malformed (bad UUID, unparseable filter)."""

    status_code = 400
    code = "bad_request"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ValidationFailedError(DomainError):
    """The request is well-formed but one or more fields break a validation rule."""

    status_code = 422
    code = "validation_error"
