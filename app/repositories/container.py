"""Container for the repository layer: everything that talks to the database."""

from dependency_injector import containers, providers

from app.repositories.call_log_repository import CallLogRepository
from app.repositories.patient_repository import PatientRepository


class RepositoryContainer(containers.DeclarativeContainer):
    # Supplied by the root container.
    database = providers.Dependency()
    utilities = providers.DependenciesContainer()

    patient_repository = providers.Singleton(
        PatientRepository, database=database, clock=utilities.clock
    )
    call_log_repository = providers.Singleton(
        CallLogRepository, database=database, clock=utilities.clock
    )
