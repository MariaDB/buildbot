from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePath

from twisted.internet import defer

from buildbot.plugins import steps, util
from buildbot.process.properties import Interpolate

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


class ShellCommandWithURL(steps.ShellCommand):
    """
    This class extend's Buildbot's base ShellCommand, to allow rendering
    an additional url in the interface.
    The URL can point to relevant artifacts for developers to use.
    """

    # Add URL and URL text to the renderables list (use with Interpolate)
    renderables = ["url", "urlText"]

    def __init__(self, url: URL = None, **kwargs):
        super().__init__(**kwargs)
        # Need to set the url and urlText so they can be rendered
        self.url = url._url if isinstance(url, URL) else None
        self.urlText = url._url_text if isinstance(url, URL) else None

    # FIXME Replace start() with run() when upgrading to Buildbot 4.x
    @defer.inlineCallbacks
    def start(self):
        if self.url is not None:
            yield self.addURL(self.urlText, self.url)

        # Return to the original method
        res = yield super().start()
        return res
