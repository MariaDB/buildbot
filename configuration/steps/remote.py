from buildbot.plugins import steps
from configuration.steps.base import PrefixableStep, StepOptions
from configuration.steps.commands.base import Command


class ShellStep(PrefixableStep):
    def __init__(
        self,
        command: Command,
        options: StepOptions = None,
        interruptSignal="TERM",
        env_vars: list[tuple] = None,
    ):
        self.command = command
        self.interruptSignal = interruptSignal
        assert isinstance(command, Command)
        super().__init__(command.name, options, env_vars=env_vars)
        self.prefix_cmd = []

    def add_cmd_prefix(self, command):
        self.prefix_cmd.extend(command)

    def generate(self):
        return steps.ShellCommand(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interruptSignal,
            **self.options.getopt,
        )


class PropFromShellStep(PrefixableStep):
    def __init__(
        self,
        command: Command,
        property,
        options: StepOptions = None,
        interruptSignal="TERM",
        env_vars: list[tuple] = None,
    ):
        self.command = command
        self.interruptSignal = interruptSignal
        self.property = property
        assert isinstance(command, Command)
        name = f"Set {self.property} from {command.name}"
        super().__init__(name, options, env_vars=env_vars)
        self.prefix_cmd = []

    def add_cmd_prefix(self, command):
        self.prefix_cmd.extend(command)

    def generate(self):
        return steps.SetPropertyFromCommand(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interruptSignal,
            property=self.property,
            **self.options.getopt,
        )


# Supports checkpointing
class DockerShellStep(ShellStep):
    def __init__(
        self,
        command: Command,
        options: StepOptions = None,
        interruptSignal="TERM",
        checkpoint: bool = False,
        env_vars: list[tuple] = None,
    ):
        self.checkpoint = checkpoint
        super().__init__(command, options, interruptSignal, env_vars)
