"""Root dependency injection container.

Each layer owns its own container, next to the classes it wires:
    app/utilities/container.py     -> UtilityContainer
    app/repositories/container.py  -> RepositoryContainer
    app/services/container.py      -> ServiceContainer

This root container composes them and passes each layer only what it is allowed to
depend on (services -> repositories -> database; utilities depend on nothing).
Everything depends on interfaces (app/interfaces), so any implementation can be
swapped in a layer's container without touching its callers.
"""

from dependency_injector import containers, providers

from app.core.config import Settings
from app.core.exception_handlers import ExceptionHandlers
from app.database.database import Database
from app.repositories.container import RepositoryContainer
from app.services.container import ServiceContainer
from app.utilities.container import UtilityContainer


class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)

    utilities = providers.Container(UtilityContainer, settings=settings)

    database = providers.Singleton(Database, url=settings.provided.database_url)

    repositories = providers.Container(
        RepositoryContainer, database=database, utilities=utilities
    )

    services = providers.Container(
        ServiceContainer, settings=settings, repositories=repositories, utilities=utilities
    )

    # HTTP layer. Routers (app/routers) pull what they need via Depends(Provide[...]).
    exception_handlers = providers.Singleton(
        ExceptionHandlers,
        responses=utilities.response_builder,
        error_formatter=utilities.error_formatter,
    )
