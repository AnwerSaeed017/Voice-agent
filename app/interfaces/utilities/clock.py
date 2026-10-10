from abc import ABC, abstractmethod
from datetime import date, datetime


class IClock(ABC):
    @abstractmethod
    def utc_now(self) -> datetime: ...

    @abstractmethod
    def today(self) -> date: ...
