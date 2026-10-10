from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-only import: app.schemas.patient itself depends on this interfaces package.
    from app.schemas.patient import PatientFilters


class IRequestParser(ABC):
    """Turns raw path and query values into typed objects, or raises BadRequestError."""

    @abstractmethod
    def patient_id(self, raw: str) -> uuid.UUID: ...

    @abstractmethod
    def patient_filters(self, raw: dict) -> PatientFilters: ...
