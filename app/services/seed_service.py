import logging

from app.interfaces.repository import IPatientRepository
from app.interfaces.service import ISeedService
from app.schemas.patient import PatientCreate


class SeedService(ISeedService):
    """Inserts two clearly fictional patients on first start so the API has data to show."""

    _logger = logging.getLogger(__name__)

    _DEMO_PATIENTS = (
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": "04/12/1988",
            "sex": "Female",
            "phone_number": "2025550143",
            "email": "jane.doe@example.com",
            "address_line_1": "123 Main Street",
            "address_line_2": "Apt 4B",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62704",
            "insurance_provider": "Blue Cross Blue Shield",
            "insurance_member_id": "XYZ123456789",
            "emergency_contact_name": "John Doe",
            "emergency_contact_phone": "2025550144",
        },
        {
            "first_name": "Miguel",
            "last_name": "O'Connor-Reyes",
            "date_of_birth": "11/03/1975",
            "sex": "Male",
            "phone_number": "2025550178",
            "address_line_1": "78 Alameda Avenue",
            "city": "Austin",
            "state": "TX",
            "zip_code": "78701-4321",
            "preferred_language": "Spanish",
        },
    )

    def __init__(self, patients: IPatientRepository, enabled: bool) -> None:
        self._patients = patients
        self._enabled = enabled

    def seed_if_empty(self) -> int:
        if not self._enabled or self._patients.count() > 0:
            return 0
        for demo_patient in self._DEMO_PATIENTS:
            self._patients.add(PatientCreate(**demo_patient).model_dump())
        self._logger.info("Seeded %d demo patients", len(self._DEMO_PATIENTS))
        return len(self._DEMO_PATIENTS)
