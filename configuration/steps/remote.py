from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from buildbot.process.results import SUCCESS, WARNINGS
from configuration.steps.base import BaseStep, StepOptions
from configuration.steps.commands.base import URL, Command, ShellCommandWithURL


class ShellStep(BaseStep):
    """
    A step that executes a shell command.
    This class is used to run shell commands as part of a build step in Buildbot.
    Attributes:
        command (Command): The command to be executed.
        options (StepOptions): Options for the step, such as timeout and retry settings.
        interrupt_signal (str): The signal to send to interrupt the command (default: "TERM").
        env_vars (list[tuple]): Environment variables to set for the command.
        secret_env_vars (list[tuple]): Like env_vars, but for credentials: InContainer
            forwards them by name (docker run -e NAME) rather than inlining them as
            -e NAME=value, so the value never lands on a command line, and logEnviron
            is turned off. Use git_auth.git_auth_env_vars().
        url (str): Optional URL to associate with the step.
        urlText (str): Optional text for the URL. Defaults to the url itself.
        timeout (int): Timeout for the command execution in seconds. Defaults to 1200 seconds.
        warn_on_fail (bool): If True, treat non-zero return codes as warnings instead of failures.
        decode_rc (dict): Return code to result, overriding warn_on_fail;
            unlisted codes fail.
        step_class (type): The buildbot step to generate, ShellCommandWithURL
            or a subclass, e.g. one that reads the output (BuildPluginsShellCommand).
    Args:
    """

    DEFAULT_DECODE_RC = {0: SUCCESS}
    WARN_ON_FAIL_DECODE_RC = {0: SUCCESS, **{i: WARNINGS for i in range(1, 256)}}
    # Best-effort commands: 0 all succeeded, 2 some did, else none did. Pair
    # with flunkOnWarnings, so a partial success still fails the build.
    PARTIAL_SUCCESS_DECODE_RC = {0: SUCCESS, 2: WARNINGS}

    def __init__(
        self,
        command: Command,
        options: StepOptions = None,
        interrupt_signal="TERM",
        env_vars: list[tuple] = None,
        secret_env_vars: list[tuple] = None,
        url: URL = None,
        timeout=1200,  # Default timeout in seconds
        warn_on_fail=False,
        decode_rc: dict = None,
        step_class: type = ShellCommandWithURL,
    ):
        if env_vars is None:
            env_vars = []
        if secret_env_vars is None:
            secret_env_vars = []
        self.command = command
        self.interrupt_signal = interrupt_signal
        self.env_vars = env_vars
        self.secret_env_vars = secret_env_vars
        self.url = url
        self.timeout = timeout
        self.step_class = step_class
        assert isinstance(command, Command)
        super().__init__(command.name, options)
        self.prefix_cmd = []
        if decode_rc is not None:
            self.decode_return_code = decode_rc
        elif warn_on_fail:
            self.decode_return_code = self.WARN_ON_FAIL_DECODE_RC
        else:
            self.decode_return_code = self.DEFAULT_DECODE_RC

    def generate(self) -> IBuildStep:
        workdir = self._set_workdir()
        return self.step_class(
            name=self.name,
            command=[*self.prefix_cmd, *self.command.as_cmd_arg()],
            interruptSignal=self.interrupt_signal,
            **self.options.getopt,
            workdir=workdir,
            url=self.url,
            timeout=self.timeout,
            env={
                k: util.Interpolate(v)
                for k, v in (*self.env_vars, *self.secret_env_vars)
            },
            # The worker dumps the environment to its own twistd.log too, and
            # only the master's copy is scrubbed. Suppress it when we carry a
            # credential, since most of our workers are long-lived.
            logEnviron=not self.secret_env_vars,
            decodeRC=self.decode_return_code,
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
        secret_env_vars (list[tuple]): Credentials, as for ShellStep.
    """

    def __init__(
        self,
        command: Command,
        property: str,
        options: StepOptions = None,
        interrupt_signal="TERM",
        env_vars: list[tuple] = None,
        secret_env_vars: list[tuple] = None,
    ):
        self.property = property
        super().__init__(
            command=command,
            options=options,
            interrupt_signal=interrupt_signal,
            env_vars=env_vars,
            secret_env_vars=secret_env_vars,
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
            env={
                k: util.Interpolate(v)
                for k, v in (*self.env_vars, *self.secret_env_vars)
            },
            # As in ShellStep.generate.
            logEnviron=not self.secret_env_vars,
        )
