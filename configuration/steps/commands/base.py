from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import PurePath

from twisted.internet import defer

from buildbot.plugins import steps, util
from buildbot.process.properties import Interpolate


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
