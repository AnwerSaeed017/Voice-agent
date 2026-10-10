"""Tools the LLM can call during a phone call.

Each one is executed by VoiceAgentService (app/services/voice_agent_service.py) when
Vapi posts a "tool-calls" message to /vapi/webhook. The descriptions are written for the
model: they say when to call the tool, not just what it does.
"""

from app.interfaces.utilities import IAgentTools


class AgentTools(IAgentTools):
    _PATIENT_PROPERTIES = {
        "first_name": {"type": "string", "description": "Letters, hyphens and apostrophes only."},
        "last_name": {"type": "string", "description": "Letters, hyphens and apostrophes only."},
        "date_of_birth": {"type": "string", "description": "MM/DD/YYYY, for example 03/05/1990."},
        "sex": {"type": "string", "enum": ["Male", "Female", "Other", "Decline to Answer"]},
        "phone_number": {"type": "string", "description": "Exactly 10 digits, no punctuation."},
        "email": {"type": "string", "description": "Optional email address."},
        "address_line_1": {"type": "string", "description": "Street address, e.g. 123 Main Street."},
        "address_line_2": {"type": "string", "description": "Optional apartment, suite or unit."},
        "city": {"type": "string"},
        "state": {"type": "string", "description": "2-letter U.S. state abbreviation, e.g. TX."},
        "zip_code": {"type": "string", "description": "5 digits, or ZIP+4 as 12345-6789."},
        "insurance_provider": {"type": "string", "description": "Optional insurance company name."},
        "insurance_member_id": {"type": "string", "description": "Optional. Letters and numbers only."},
        "preferred_language": {"type": "string", "description": "Optional. Defaults to English."},
        "emergency_contact_name": {"type": "string", "description": "Optional full name."},
        "emergency_contact_phone": {"type": "string", "description": "Optional. Exactly 10 digits."},
    }

    _REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone_number",
        "address_line_1",
        "city",
        "state",
        "zip_code",
    ]

    def definitions(self) -> list[dict]:
        return [
            self._function_tool(
                name="check_existing_patient",
                description=(
                    "Look up whether a patient record already exists for a phone number. "
                    "Call once, as soon as the caller has given a valid 10-digit phone number."
                ),
                properties={"phone_number": self._PATIENT_PROPERTIES["phone_number"]},
                required=["phone_number"],
                hold_phrase="Thanks, one moment.",
            ),
            self._function_tool(
                name="save_patient",
                description=(
                    "Save a new patient registration. Call only after reading every detail "
                    "back to the caller and hearing them confirm it is all correct."
                ),
                properties=self._PATIENT_PROPERTIES,
                required=self._REQUIRED_FIELDS,
                hold_phrase="Great, give me just a moment while I save that.",
            ),
            self._function_tool(
                name="update_patient",
                description=(
                    "Update an existing patient record found by check_existing_patient. "
                    "Send the patient_id and only the details that changed, after the "
                    "caller has confirmed the changes."
                ),
                properties={
                    "patient_id": {
                        "type": "string",
                        "description": "The patient_id returned by check_existing_patient.",
                    },
                    **self._PATIENT_PROPERTIES,
                },
                required=["patient_id"],
                hold_phrase="One moment while I update your record.",
            ),
            # Built into Vapi: lets the model hang up after the closing line.
            {"type": "endCall"},
        ]

    @staticmethod
    def _function_tool(
        name: str, description: str, properties: dict, required: list[str], hold_phrase: str
    ) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
            # Spoken while the webhook runs, so the caller never sits in dead air.
            "messages": [{"type": "request-start", "content": hold_phrase}],
        }
