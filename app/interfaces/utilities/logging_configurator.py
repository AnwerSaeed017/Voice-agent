from abc import ABC, abstractmethod


class ILoggingConfigurator(ABC):
    @abstractmethod
    def configure(self) -> None: ...
