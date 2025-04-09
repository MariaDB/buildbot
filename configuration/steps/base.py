from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass

from configuration.steps.commands.base import Command


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
    def __init__(self, name, options):
        self.name = name
        if options is None:
            self.options = StepOptions()  # Load default options
        else:
            assert isinstance(options, StepOptions)
            self.options = options

    @abstractmethod
    def generate(self): ...


class PrefixableStep(BaseStep):
    def __init__(self, name, options, env_vars):
        self.env_vars = env_vars
        super().__init__(name, options)

    @abstractmethod
    def add_cmd_prefix(self, command: Command): ...
