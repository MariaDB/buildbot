from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from typing import Optional


@dataclass
class StepOptions:  # all step (shell, compile, etc) types support these options
    """
    Options for a build step.
    This class defines the options that can be applied to a build step,
    such as whether it should always run, halt on failure, and custom run conditions.
    Attributes:
        alwaysRun (bool): If True, the step will always run regardless of previous failures.
        haltOnFailure (bool): If True, the build will halt if this step fails.
        flunkOnWarnings (bool): If True, a step ending in WARNINGS fails the
            build, which carries on; the step itself stays a warning.
        doStepIf (callable): A callable that determines if the step should be executed.
    """

    # Default : safety first
    alwaysRun: bool = False
    haltOnFailure: bool = True
    flunkOnWarnings: bool = False
    doStepIf: callable = lambda _: True
    description: str = None
    descriptionDone: str = None

    @property
    def getopt(self):
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_") and value is not None
        }


class BaseStep(ABC):
    def __init__(self, name: str, options: Optional[StepOptions] = None):
        self.name = name
        self.options = options
        if self.options is None:
            self.options = StepOptions()  # Load default options
        assert isinstance(self.options, StepOptions)

    @abstractmethod
    def generate(self): ...
