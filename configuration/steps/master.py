from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps
from configuration.steps.base import BaseStep, StepOptions
from configuration.steps.commands.base import Command


class MasterShellStep(BaseStep):
    """
    A step that executes a shell command on the master.
    This class is used to run shell commands as part of a build step in Buildbot,
    specifically on the master node.
    Attributes:
        command (Command): The command to be executed.
        options (StepOptions): Options for the step, such as timeout and retry settings.
        interrupt_signal (str): The signal to send to interrupt the command (default: "TERM").
        env_vars (list[tuple]): Environment variables to set for the command.
    """

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
