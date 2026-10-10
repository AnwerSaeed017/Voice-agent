"""Builds the Vapi assistant definition, so the agent is configured from code in this
repo rather than by hand in a dashboard."""

from app.core.config import Settings
from app.interfaces.utilities import IAgentPrompt, IAgentTools, IAssistantConfigBuilder


class AssistantConfigBuilder(IAssistantConfigBuilder):
    ASSISTANT_NAME = "Patient Registration Agent"

    def __init__(self, settings: Settings, prompt: IAgentPrompt, tools: IAgentTools) -> None:
        self._settings = settings
        self._prompt = prompt
        self._tools = tools

    def build(self) -> dict:
        return {
            "name": self.ASSISTANT_NAME,
            "firstMessage": self._prompt.first_message(),
            "firstMessageMode": "assistant-speaks-first",
            "model": {
                "provider": self._settings.vapi_model_provider,
                "model": self._settings.vapi_model,
                # Low temperature: the wording can vary, the collected data must not.
                "temperature": 0.3,
                "messages": [{"role": "system", "content": self._prompt.system_prompt()}],
                "tools": self._tools.definitions(),
            },
            "voice": {
                "provider": self._settings.vapi_voice_provider,
                "voiceId": self._settings.vapi_voice_id,
            },
            "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
            # One webhook receives tool calls during the call and the report after it.
            "server": self._server(),
            "serverMessages": ["tool-calls", "end-of-call-report"],
            # Vapi hangs up when the agent says this. It replaces an endCall tool, which the
            # model either never called or called before speaking its closing line.
            "endCallPhrases": ["goodbye"],
            "silenceTimeoutSeconds": 30,
            "maxDurationSeconds": 900,
        }

    def _server(self) -> dict:
        server = {
            "url": f"{self._settings.public_base_url}/vapi/webhook",
            "timeoutSeconds": 20,
        }
        if self._settings.vapi_webhook_secret:
            server["headers"] = {"X-Vapi-Secret": self._settings.vapi_webhook_secret}
        return server
