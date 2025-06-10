from abc import ABC, abstractmethod
from pathlib import PurePath

from twisted.internet import defer

from buildbot.plugins import steps


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


class ShellCommandWithURL(steps.ShellCommand):
    def __init__(self, url=None, urlText=None, **kwargs):
        super().__init__(**kwargs)
        # Add URL and URL text to the renderables list (use with Interpolate)
        self.renderables.append("url")
        self.renderables.append("urlText")
        self.url = url
        self.urlText = urlText

    # FIXME Replace start() with run() when upgrading to Buildbot 4.x
    @defer.inlineCallbacks
    def start(self):
        if self.url is not None:
            urlText = self.urlText

            if urlText is None:
                urlText = self.url

            yield self.addURL(urlText, self.url)

        # Return to the original method
        res = yield super().start()
        return res
