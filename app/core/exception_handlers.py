"""Maps every failure onto the { data, error } envelope with the right status code."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DomainError
from app.interfaces.utilities import IResponseBuilder, IValidationErrorFormatter


class ExceptionHandlers:
    _logger = logging.getLogger(__name__)

    _HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}

    def __init__(
        self, responses: IResponseBuilder, error_formatter: IValidationErrorFormatter
    ) -> None:
        self._responses = responses
        self._error_formatter = error_formatter

    def register(self, app: FastAPI) -> None:
        app.add_exception_handler(DomainError, self._handle_domain_error)
        app.add_exception_handler(RequestValidationError, self._handle_request_validation)
        app.add_exception_handler(StarletteHTTPException, self._handle_http_exception)
        app.add_exception_handler(Exception, self._handle_unexpected)

    async def _handle_domain_error(self, request: Request, exc: DomainError) -> JSONResponse:
        return self._responses.error(exc.status_code, exc.code, exc.message, exc.details)

    async def _handle_request_validation(
        self, request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        # A body that is not parseable JSON is a malformed request (400), not a rule violation (422).
        if any(error.get("type") == "json_invalid" for error in errors):
            return self._responses.error(400, "bad_request", "Request body is not valid JSON.")
        return self._responses.error(
            422,
            "validation_error",
            "One or more fields are invalid.",
            self._error_formatter.format(errors),
        )

    async def _handle_http_exception(
        self, request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = self._HTTP_CODES.get(exc.status_code, "http_error")
        return self._responses.error(exc.status_code, code, str(exc.detail))

    async def _handle_unexpected(self, request: Request, exc: Exception) -> JSONResponse:
        self._logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return self._responses.error(500, "internal_error", "An unexpected error occurred.")
