from abc import ABC, abstractmethod
from pathlib import PurePath


class Command(ABC):
    """
    Base class for commands executed in the build process.
    This class defines the structure for commands that can be run as part of a build step.
    Attributes:
        name (str): The name of the command.
        workdir (PurePath): The working directory where the command will be executed.
        user (str): The user under which the command will run (default: "buildbot").
    """

    def __init__(self, name, workdir: PurePath, user: str = "buildbot"):
        self.name = name
        self.workdir = workdir
        self.user = user

    @abstractmethod
    def as_cmd_arg(self) -> list[str]:
        pass
