import httpx

from app.interfaces.utilities import IVapiClient


class VapiClient(IVapiClient):
    """Thin wrapper over the Vapi REST API (https://api.vapi.ai)."""

    _BASE_URL = "https://api.vapi.ai"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def list_assistants(self) -> list[dict]:
        return self._request("GET", "/assistant")

    def create_assistant(self, config: dict) -> dict:
        return self._request("POST", "/assistant", config)

    def update_assistant(self, assistant_id: str, config: dict) -> dict:
        return self._request("PATCH", f"/assistant/{assistant_id}", config)

    def list_phone_numbers(self) -> list[dict]:
        return self._request("GET", "/phone-number")

    def create_phone_number(self, config: dict) -> dict:
        return self._request("POST", "/phone-number", config)

    def update_phone_number(self, phone_number_id: str, config: dict) -> dict:
        return self._request("PATCH", f"/phone-number/{phone_number_id}", config)

    def _request(self, method: str, path: str, body: dict | None = None):
        if not self._api_key:
            raise RuntimeError("VAPI_API_KEY is not set (see .env.example).")
        response = httpx.request(
            method,
            self._BASE_URL + path,
            json=body,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=30,
        )
        if response.status_code >= 400:
            # Vapi's validation messages name the offending field; surface them as-is.
            raise RuntimeError(f"Vapi {method} {path} failed ({response.status_code}): {response.text}")
        return response.json()
