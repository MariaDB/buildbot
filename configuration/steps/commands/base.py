from abc import ABC, abstractmethod


class Command(ABC):
    def __init__(self, name, workdir: str, user: str = "buildbot"):
        self.name = name
        self.workdir = workdir
        self.user = user

    @abstractmethod
    def as_cmd_arg(self) -> list[str]:
        pass
