import logging

from app.constants.constants import DEMO_PATIENTS
from app.interfaces.repository import IPatientRepository
from app.interfaces.service import ISeedService
from app.schemas.patient import PatientCreate


class SeedService(ISeedService):
    """Inserts two clearly fictional patients on first start so the API has data to show."""

    _logger = logging.getLogger(__name__)

    def __init__(self, patients: IPatientRepository, enabled: bool) -> None:
        self._patients = patients
        self._enabled = enabled

    def seed_if_empty(self) -> int:
        if not self._enabled or self._patients.count() > 0:
            return 0
        for demo_patient in DEMO_PATIENTS:
            self._patients.add(PatientCreate(**demo_patient).model_dump())
        self._logger.info("Seeded %d demo patients", len(DEMO_PATIENTS))
        return len(DEMO_PATIENTS)
