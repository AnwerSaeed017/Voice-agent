"""The agent's prompt, tools and Vapi configuration, as built from the code in app/voice_agent."""

import pytest

from app.constants.constants import ASSISTANT_NAME
from app.voice_agent.agent_prompt import AgentPrompt
from app.voice_agent.agent_tools import AgentTools
from app.voice_agent.assistant_config_builder import AssistantConfigBuilder


class FakeSettings:
    public_base_url = "https://example.test"
    vapi_webhook_secret = "s3cret"
    clinic_name = "Test Clinic"
    vapi_model_provider = "openai"
    vapi_model = "gpt-4.1"
    vapi_voice_provider = "vapi"
    vapi_voice_id = "Clara"


@pytest.fixture(scope="module")
def prompt() -> AgentPrompt:
    return AgentPrompt(clinic_name="Test Clinic")


@pytest.fixture(scope="module")
def config(prompt) -> dict:
    return AssistantConfigBuilder(settings=FakeSettings(), prompt=prompt, tools=AgentTools()).build()


def tool(config: dict, name: str) -> dict:
    return next(entry["function"] for entry in config["model"]["tools"] if entry.get("function", {}).get("name") == name)


class TestPrompt:
    def test_names_the_clinic_in_the_prompt_and_the_greeting(self, prompt):
        assert "Test Clinic" in prompt.system_prompt()
        assert "Test Clinic" in prompt.first_message()

    @pytest.mark.parametrize("rule", [
        "read all of it back",                      # confirmation before saving
        "both the first name and the last name spelled letter by letter",  # misheard names
        "Do not speak first",                       # save immediately after the caller's yes
        "only when save_patient or update_patient has returned success true",
        "Thanks for calling. Goodbye.",             # fixed closing line that ends the call
        "discard everything collected so far",      # starting over
        "five one two, five five five",             # digits spoken as words
        "call 911",                                 # emergencies
    ])
    def test_carries_the_rules_the_brief_and_the_test_calls_require(self, prompt, rule):
        assert rule in prompt.system_prompt()

    def test_includes_the_date_time_and_caller_id_placeholders(self, prompt):
        text = prompt.system_prompt()
        assert '{{"now" | date: "%A, %B %d, %Y", "America/New_York"}}' in text
        assert '{{"now" | date: "%I:%M %p", "America/New_York"}}, Eastern Time' in text
        assert "{{customer.number}}" in text

    def test_tells_the_agent_it_may_give_the_date_and_time(self, prompt):
        assert "asks for the date or the time, tell them" in prompt.system_prompt()


class TestTools:
    def test_exactly_the_three_registration_tools(self, config):
        names = [entry.get("function", {}).get("name", entry["type"]) for entry in config["model"]["tools"]]
        assert names == ["check_existing_patient", "save_patient", "update_patient"]

    def test_save_requires_every_required_field_and_the_confirmation_flag(self, config):
        required = set(tool(config, "save_patient")["parameters"]["required"])
        assert required == {"first_name", "last_name", "date_of_birth", "sex", "phone_number",
                            "address_line_1", "city", "state", "zip_code", "read_back_confirmed"}

    def test_update_requires_the_record_id_and_the_confirmation_flag(self, config):
        assert set(tool(config, "update_patient")["parameters"]["required"]) == {"patient_id", "read_back_confirmed"}

    def test_sex_is_limited_to_the_four_values(self, config):
        sex = tool(config, "save_patient")["parameters"]["properties"]["sex"]
        assert sex["enum"] == ["Male", "Female", "Other", "Decline to Answer"]


class TestAssistantConfig:
    def test_points_vapi_at_the_webhook_with_the_shared_secret(self, config):
        assert config["server"]["url"] == "https://example.test/vapi/webhook"
        assert config["server"]["headers"] == {"X-Vapi-Secret": "s3cret"}

    def test_ends_the_call_on_the_closing_word(self, config):
        assert config["endCallPhrases"] == ["goodbye"]

    def test_uses_the_configured_model_and_voice(self, config):
        assert (config["name"], config["model"]["model"], config["voice"]["voiceId"]) == (ASSISTANT_NAME, "gpt-4.1", "Clara")
        assert config["serverMessages"] == ["tool-calls", "end-of-call-report"]
