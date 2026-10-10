from abc import ABC, abstractmethod


class IAgentPrompt(ABC):
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def first_message(self) -> str: ...
