from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps
from configuration.steps.base import BaseStep, StepOptions
from configuration.steps.commands.base import Command


class MasterShellStep(BaseStep):
    def __init__(
        self,
        command: Command,
        options: StepOptions = None,
        interrupt_signal="TERM",
        env_vars: list[tuple] = None,
    ):
        if env_vars is None:
            env_vars = []
        self.command = command
        self.interrupt_signal = interrupt_signal
        self.env_vars = env_vars
        assert isinstance(command, Command)
        super().__init__(command.name, options)
        self.prefix_cmd = []

    def generate(self) -> IBuildStep:
        return steps.MasterShellCommand(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interrupt_signal,
            **self.options.getopt,
        )
