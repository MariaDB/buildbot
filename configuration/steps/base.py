from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from typing import Optional


@dataclass
class StepOptions:  # all step (shell, compile, etc) types support these options
    # Default : safety first
    alwaysRun: bool = False
    haltOnFailure: bool = True
    doStepIf: callable = lambda _: True

    @property
    def getopt(self):
        Options = namedtuple("Options", ["alwaysRun", "haltOnFailure", "doStepIf"])
        return Options(self.alwaysRun, self.haltOnFailure, self.doStepIf)._asdict()


class BaseStep(ABC):
    def __init__(self, name: str, options: Optional[StepOptions] = None):
        self.name = name
        self.run_in_container = False
        self.container_commit = False
        self.docker_environment = None
        self.options = options
        if self.options is None:
            self.options = StepOptions()  # Load default options
        assert isinstance(self.options, StepOptions)

    @abstractmethod
    def generate(self): ...
