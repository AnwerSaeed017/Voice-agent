"""Container for the utilities layer: stateless helpers with no database access."""

from dependency_injector import containers, providers

from app.utilities.clock import UtcClock
from app.utilities.field_normalizer import FieldNormalizer
from app.utilities.logging_configurator import StdoutLoggingConfigurator
from app.utilities.request_parser import RequestParser
from app.utilities.response_builder import ResponseBuilder
from app.utilities.secret_verifier import SharedSecretVerifier
from app.utilities.sql_loader import SqlFileLoader
from app.utilities.validation_error_formatter import ValidationErrorFormatter
from app.voice.agent_prompt import AgentPrompt
from app.voice.agent_tools import AgentTools
from app.voice.assistant_config_builder import AssistantConfigBuilder
from app.voice.vapi_client import VapiClient


class UtilityContainer(containers.DeclarativeContainer):
    # Supplied by the root container.
    settings = providers.Dependency()

    clock = providers.Singleton(UtcClock)
    logging_configurator = providers.Singleton(StdoutLoggingConfigurator)
    field_normalizer = providers.Singleton(FieldNormalizer, clock=clock)
    error_formatter = providers.Singleton(ValidationErrorFormatter)
    response_builder = providers.Singleton(ResponseBuilder)
    request_parser = providers.Singleton(RequestParser, error_formatter=error_formatter)
    sql_loader = providers.Singleton(SqlFileLoader)
    secret_verifier = providers.Singleton(
        SharedSecretVerifier, expected=settings.provided.vapi_webhook_secret
    )

    # Voice agent definition and the Vapi API client
    agent_prompt = providers.Singleton(AgentPrompt, clinic_name=settings.provided.clinic_name)
    agent_tools = providers.Singleton(AgentTools)
    assistant_config_builder = providers.Singleton(
        AssistantConfigBuilder, settings=settings, prompt=agent_prompt, tools=agent_tools
    )
    vapi_client = providers.Singleton(VapiClient, api_key=settings.provided.vapi_api_key)
