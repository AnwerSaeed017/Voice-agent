from abc import ABC, abstractmethod

from fastapi.responses import JSONResponse


class IResponseBuilder(ABC):
    @abstractmethod
    def success(self, data: object, status_code: int = 200) -> JSONResponse: ...

    @abstractmethod
    def error(
        self, status_code: int, code: str, message: str, details: list[dict] | None = None
    ) -> JSONResponse: ...
