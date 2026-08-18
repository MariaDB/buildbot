from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePath

from twisted.internet import defer

from buildbot.plugins import steps, util
from buildbot.process import remotecommand
from buildbot.process.properties import Interpolate
from buildbot.process.results import CANCELLED, EXCEPTION, FAILURE, RETRY
from buildbot.util import flatten

# Use if you need to load script files to commands
COMMAND_SCRIPT_BASE_DIR = Path(__file__).parent / "scripts"


def load_script(script_name) -> str:
    script_path = COMMAND_SCRIPT_BASE_DIR / script_name
    with open(script_path, "r") as f:
        script = f.read()
    return script


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


class BashScriptCommand(Command):
    def __init__(
        self,
        script_name: str,
        args: list[str] = None,
        user: str = "buildbot",
        workdir: PurePath = PurePath("."),
    ):
        name = f"Run {script_name}"
        super().__init__(name=name, workdir=workdir, user=user)
        self.script_name = script_name
        self.args = args if args is not None else []

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            load_script(script_name=self.script_name),
            "--",
            *self.args,
        ]


class BashCommand(Command):
    def __init__(
        self,
        cmd: str,
        name: str = "Run command",
        user: str = "buildbot",
        workdir: PurePath = PurePath("."),
    ):
        super().__init__(name=name, workdir=workdir, user=user)
        self.cmd = cmd

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(self.cmd),
        ]


class PowerShellCommand(Command):
    def __init__(
        self,
        cmd: str,
        name: str = "Run command",
        user: str = "buildbot",
        workdir: PurePath = PurePath("."),
    ):
        super().__init__(name=name, workdir=workdir, user=user)
        self.cmd = cmd

    def as_cmd_arg(self) -> list[str]:
        return [
            "powershell",
            "-Command",
            util.Interpolate(self.cmd),
        ]


@dataclass
class URL:
    url: str
    url_text: str = None

    @property
    def _url(self) -> Interpolate:
        return util.Interpolate(self.url)

    @property
    def _url_text(self) -> Interpolate:
        return (
            util.Interpolate(self.url_text)
            if self.url_text
            else util.Interpolate(self.url)
        )


_TERMINAL_RESULTS = (EXCEPTION, RETRY, CANCELLED)


def _iterFailureCommands(specifications):
    """Validate and yield named failure commands."""

    used_names = set()

    for specification in specifications:
        if not isinstance(specification, dict):
            raise TypeError("each commandsOnFailure entry must be a dictionary")

        if "name" not in specification:
            raise TypeError("each commandsOnFailure entry requires 'name'")

        if "command" not in specification:
            raise TypeError("each commandsOnFailure entry requires 'command'")

        name = specification["name"]
        command = specification["command"]

        if not isinstance(name, str) or not name:
            raise TypeError("failure command name must be a non-empty string")

        if name in used_names:
            raise ValueError("duplicate failure command name: {!r}".format(name))

        used_names.add(name)

        yield {
            "name": name,
            "logName": "stdio {}".format(name),
            "command": command,
        }


class _CustomShellCommandBase(steps.ShellCommand):
    """Common configuration for the Buildbot 2.7 and 4.x variants."""

    # Parent renderables are accumulated by Buildbot, so only the new
    # attributes need to be listed here.
    renderables = [
        "url",
        "urlText",
        "commandsOnFailure",
    ]

    def __init__(self, url=None, commandsOnFailure=None, **kwargs):
        if url is not None and not isinstance(url, URL):
            raise TypeError("url must be a URL instance or None")

        super().__init__(**kwargs)

        if url is None:
            self.url = None
            self.urlText = None
        else:
            self.url = url._url
            self.urlText = url._url_text

        if commandsOnFailure is None:
            self.commandsOnFailure = []
        else:
            self.commandsOnFailure = commandsOnFailure


if hasattr(steps.ShellCommand, "makeRemoteShellCommand"):
    # Buildbot 4.x:
    # ShellCommand inherits ShellMixin and implements run().

    class CustomShellCommand(_CustomShellCommandBase):

        @defer.inlineCallbacks
        def run(self):
            if self.url is not None:
                yield self.addURL(self.urlText, self.url)

            # Run the primary command using the normal ShellCommand logic.
            primary_result = yield super().run()

            # Run failure commands only for a genuine FAILURE.
            if primary_result != FAILURE:
                return primary_result

            final_result = primary_result

            # makeRemoteShellCommand changes self.command. It also uses
            # self.logfiles while setting up logs, even if logfiles={} is
            # supplied as an override.
            primary_command = self.command
            primary_logfiles = self.logfiles

            try:
                # The primary command's watched files must not be attached
                # again to every failure command.
                self.logfiles = {}

                for specification in _iterFailureCommands(self.commandsOnFailure):
                    failure_command = yield self.makeRemoteShellCommand(
                        command=specification["command"],
                        stdioLogName=specification["logName"],
                        logfiles={},
                    )

                    yield self.runCommand(failure_command)

                    handler_result = failure_command.results()

                    # An ordinary nonzero exit is ignored, and processing
                    # continues with the next failure command. Infrastructure
                    # errors and cancellation stop the sequence.
                    if handler_result in _TERMINAL_RESULTS:
                        final_result = handler_result
                        break
            finally:
                self.command = primary_command
                self.logfiles = primary_logfiles

            return final_result

else:
    # Buildbot 2.7:
    # ShellCommand is legacy-style and implements start().

    class CustomShellCommand(_CustomShellCommandBase):

        @defer.inlineCallbacks
        def start(self):
            if self.url is not None:
                yield self.addURL(self.urlText, self.url)

            # Construct the primary command using Buildbot 2.7's
            # ShellCommand implementation.
            warnings = []
            kwargs = self.buildCommandKwargs(warnings)

            primary_command = remotecommand.RemoteShellCommand(**kwargs)
            self.setupEnvironment(primary_command)

            self.stdio_log = primary_log = self.addLog("stdio")
            primary_command.useLog(
                primary_log,
                closeWhenFinished=True,
            )

            for warning in warnings:
                primary_log.addHeader(warning)

            self.setupLogfiles(primary_command, self.logfiles)

            yield self.runCommand(primary_command)

            yield defer.maybeDeferred(
                self.commandComplete,
                primary_command,
            )

            yield defer.maybeDeferred(
                self.createSummary,
                primary_command.logs["stdio"],
            )

            primary_result = yield defer.maybeDeferred(
                self.evaluateCommand,
                primary_command,
            )

            final_result = primary_result

            # Do not run for EXCEPTION, RETRY, CANCELLED, WARNINGS,
            # SUCCESS, or SKIPPED.
            if primary_result == FAILURE:
                for specification in _iterFailureCommands(self.commandsOnFailure):
                    log_name = specification["logName"]

                    warnings = []
                    kwargs = self.buildCommandKwargs(warnings)
                    kwargs["command"] = flatten(
                        specification["command"],
                        (list, tuple),
                    )

                    # Do not attach the primary command's watched files.
                    kwargs["logfiles"] = {}

                    # The remote stdio name must match the Buildbot log name.
                    kwargs["stdioLogName"] = log_name

                    failure_command = remotecommand.RemoteShellCommand(**kwargs)
                    self.setupEnvironment(failure_command)

                    failure_log = self.addLog(log_name)
                    failure_command.useLog(
                        failure_log,
                        closeWhenFinished=True,
                        logfileName=log_name,
                    )

                    for warning in warnings:
                        failure_log.addHeader(warning)

                    yield self.runCommand(failure_command)

                    handler_result = failure_command.results()

                    if handler_result in _TERMINAL_RESULTS:
                        final_result = handler_result
                        break

            yield self.setStatus(primary_command, final_result)
            return final_result
