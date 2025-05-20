from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps
from configuration.steps.base import BaseStep, StepOptions
from configuration.steps.commands.base import Command


class ShellStep(BaseStep):
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
        workdir = self._set_workdir()
        return steps.ShellCommand(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interrupt_signal,
            **self.options.getopt,
            workdir=workdir,
        )

    def _set_workdir(self) -> str:
        if self.command.workdir.is_absolute():
            workdir = self.command.workdir
        else:
            workdir = "build" / self.command.workdir
        return str(workdir)


class PropFromShellStep(ShellStep):
    def __init__(
        self,
        command: Command,
        property: str,
        options: StepOptions = None,
        interrupt_signal="TERM",
        env_vars: list[tuple] = None,
    ):
        self.property = property
        super().__init__(
            command=command,
            options=options,
            interrupt_signal=interrupt_signal,
            env_vars=env_vars,
        )
        self.name = f"Set {self.property} from {command.name}"

    def generate(self) -> IBuildStep:
        workdir = self._set_workdir()
        return steps.SetPropertyFromCommand(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interrupt_signal,
            property=self.property,
            **self.options.getopt,
            workdir=workdir,
        )
