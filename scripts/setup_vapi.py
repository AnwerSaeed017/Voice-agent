"""Create or update the Vapi assistant and its phone number.

Run from the project root, and again after any change to the prompt or tools:

    python -m scripts.setup_vapi              # assistant + phone number
    python -m scripts.setup_vapi --no-phone   # assistant only
"""

import argparse

from app.containers.container import Container


class VapiSetupCommand:
    def __init__(self) -> None:
        self._container = Container()
        self._container.utilities.logging_configurator().configure()

    def run(self) -> None:
        arguments = self._parse_arguments()
        settings = self._container.settings()
        if not settings.public_base_url:
            raise SystemExit(
                "PUBLIC_BASE_URL is not set. Vapi needs the public HTTPS URL of this "
                "service to reach /vapi/webhook."
            )

        provisioning = self._container.services.vapi_provisioning_service()
        assistant = provisioning.sync_assistant()
        print(f"Assistant: {assistant['id']} ({assistant['name']})")
        print(f"Webhook:   {settings.public_base_url}/vapi/webhook")

        if arguments.no_phone:
            return
        phone_number = provisioning.ensure_phone_number(assistant["id"])
        print(f"Phone:     {phone_number.get('number') or phone_number.get('id')}")

    @staticmethod
    def _parse_arguments() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
        parser.add_argument(
            "--no-phone", action="store_true", help="Only sync the assistant; do not touch phone numbers."
        )
        return parser.parse_args()


if __name__ == "__main__":
    VapiSetupCommand().run()
