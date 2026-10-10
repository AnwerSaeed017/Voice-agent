import logging

from app.core.config import Settings
from app.interfaces.service import IVapiProvisioningService
from app.interfaces.utilities import IAssistantConfigBuilder, IVapiClient


class VapiProvisioningService(IVapiProvisioningService):
    """Idempotent setup of the Vapi side: safe to run again after every prompt change."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self, client: IVapiClient, config_builder: IAssistantConfigBuilder, settings: Settings
    ) -> None:
        self._client = client
        self._config_builder = config_builder
        self._settings = settings

    def sync_assistant(self) -> dict:
        config = self._config_builder.build()
        existing = next(
            (
                assistant
                for assistant in self._client.list_assistants()
                if assistant.get("name") == config["name"]
            ),
            None,
        )
        if existing:
            self._logger.info("Updating assistant %s", existing["id"])
            return self._client.update_assistant(existing["id"], config)
        self._logger.info("Creating assistant '%s'", config["name"])
        return self._client.create_assistant(config)

    def ensure_phone_number(self, assistant_id: str) -> dict:
        phone_numbers = self._client.list_phone_numbers()
        attached = next(
            (number for number in phone_numbers if number.get("assistantId") == assistant_id), None
        )
        if attached:
            return attached
        if phone_numbers:
            # Reuse a number the account already owns rather than buying another.
            self._logger.info("Attaching existing number %s", phone_numbers[0].get("number"))
            return self._client.update_phone_number(
                phone_numbers[0]["id"], {"assistantId": assistant_id}
            )
        self._logger.info("Requesting a new number in area code %s", self._settings.vapi_area_code)
        return self._client.create_phone_number(
            {
                "provider": "vapi",
                "name": "Patient Registration Line",
                "numberDesiredAreaCode": self._settings.vapi_area_code,
                "assistantId": assistant_id,
            }
        )
