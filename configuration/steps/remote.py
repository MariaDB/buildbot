from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from configuration.steps.base import BaseStep, StepOptions
from configuration.steps.commands.base import Command, ShellCommandWithURL


class ShellStep(BaseStep):
    """
    A step that executes a shell command.
    This class is used to run shell commands as part of a build step in Buildbot.
    Attributes:
        command (Command): The command to be executed.
        options (StepOptions): Options for the step, such as timeout and retry settings.
        interrupt_signal (str): The signal to send to interrupt the command (default: "TERM").
        env_vars (list[tuple]): Environment variables to set for the command.
        url (str): Optional URL to associate with the step.
        urlText (str): Optional text for the URL. Defaults to the url itself.
    """

    def __init__(
        self,
        command: Command,
        options: StepOptions = None,
        interrupt_signal="TERM",
        env_vars: list[tuple] = None,
        url=None,
        url_text=None,
        timeout=1200,  # Default timeout in seconds
    ):
        if env_vars is None:
            env_vars = []
        self.command = command
        self.interrupt_signal = interrupt_signal
        self.env_vars = env_vars
        self.url = url
        self.url_text = url_text
        self.timeout = timeout
        assert isinstance(command, Command)
        super().__init__(command.name, options)
        self.prefix_cmd = []

    def generate(self) -> IBuildStep:
        workdir = self._set_workdir()
        return ShellCommandWithURL(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interrupt_signal,
            **self.options.getopt,
            workdir=workdir,
            url=util.Interpolate(self.url) if self.url else None,
            urlText=util.Interpolate(self.url_text) if self.url_text else None,
            timeout=self.timeout,
            env={k: util.Interpolate(v) for k, v in self.env_vars},
        )

    def _set_workdir(self) -> str:
        if self.command.workdir.is_absolute():
            workdir = self.command.workdir
        else:
            workdir = "build" / self.command.workdir
        return str(workdir)


class PropFromShellStep(ShellStep):
    """
    A step that sets a property from the output of a shell command.
    This class is used to execute a shell command and set a build property based on its output.
    Attributes:
        command (Command): The command to be executed.
        property (str): The property to set from the command output.
        options (StepOptions): Options for the step, such as timeout and retry settings.
        interrupt_signal (str): The signal to send to interrupt the command (default: "TERM").
        env_vars (list[tuple]): Environment variables to set for the command.
    """

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
