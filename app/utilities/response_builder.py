from fastapi.responses import JSONResponse

from app.interfaces.utilities import IResponseBuilder


class ResponseBuilder(IResponseBuilder):
    """Every API response uses the same envelope: {"data": ..., "error": ...}."""

    def success(self, data: object, status_code: int = 200) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"data": data, "error": None})

    def error(
        self, status_code: int, code: str, message: str, details: list[dict] | None = None
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "data": None,
                "error": {"code": code, "message": message, "details": details or []},
            },
        )
