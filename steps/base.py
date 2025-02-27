from abc import ABC, abstractmethod


class Command(ABC):
    def __init__(self, name: str, workdir: str):
        self.name = name
        self.workdir = workdir

    @abstractmethod
    def as_cmd_arg(self) -> list[str]:
        pass
