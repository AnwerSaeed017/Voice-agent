"""Container for the service layer: business logic, built on repositories and utilities."""

from dependency_injector import containers, providers

from app.services.call_log_service import CallLogService
from app.services.patient_service import PatientService
from app.services.seed_service import SeedService
from app.services.vapi_provisioning_service import VapiProvisioningService
from app.services.voice_agent_service import VoiceAgentService


class ServiceContainer(containers.DeclarativeContainer):
    # Supplied by the root container.
    settings = providers.Dependency()
    repositories = providers.DependenciesContainer()
    utilities = providers.DependenciesContainer()

    patient_service = providers.Singleton(
        PatientService, patients=repositories.patient_repository
    )
    call_log_service = providers.Singleton(
        CallLogService, call_logs=repositories.call_log_repository
    )
    seed_service = providers.Singleton(
        SeedService,
        patients=repositories.patient_repository,
        enabled=settings.provided.seed_demo_data,
    )
    voice_agent_service = providers.Singleton(
        VoiceAgentService,
        patients=patient_service,
        call_logs=call_log_service,
        normalizer=utilities.field_normalizer,
        error_formatter=utilities.error_formatter,
    )
    # Used by scripts/setup_vapi.py to create the assistant and phone number.
    vapi_provisioning_service = providers.Singleton(
        VapiProvisioningService,
        client=utilities.vapi_client,
        config_builder=utilities.assistant_config_builder,
        settings=settings,
    )
