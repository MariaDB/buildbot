from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command
from utils import read_template


# TODO (Razvan):This is a copy-paste only to showcase a full factory. Re-work needed.
class FetchTarball(Command):
    """
    A command to download and unpack a source tarball.
    This command retrieves a source tarball from a specified URL,
    unpacks it, and prepares the source code for further processing.
    Attributes:
        workdir (PurePath): The working directory where the tarball will be downloaded and unpacked.
    """

    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Download and unpack source tarball", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            util.Interpolate(read_template("get_tarball")),
        ]


# TODO (Razvan):This is a copy-paste only to showcase a full factory. Re-work needed.
class FetchCompat(Command):
    """
    A command to fetch MariaDB compatibility RPMs.
    This command downloads MariaDB compatibility RPMs from a specified URL
    and prepares them for use in the build process.
    Attributes:
        rpm_type (str): The type of RPM to fetch
        arch (str): The architecture for which the RPMs are intended (e.g., "x86_64").
        url (str): The URL from which to download the RPMs.
        workdir (PurePath): The working directory where the RPMs will be downloaded.
    """

    def __init__(
        self,
        rpm_type: str,
        arch: str,
        url: str,
        workdir: PurePath = PurePath("."),
    ):
        super().__init__(name="Fetch MariaDB compat RPMs", workdir=workdir)
        self.rpm_type = rpm_type
        self.arch = arch
        self.url = url

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            util.Interpolate(
                f'ls -l && ls -l ../ && wget --no-check-certificate -cO MariaDB-shared-5.3.{self.arch}.rpm "{self.url}/helper_files/mariadb-shared-5.3-{self.arch}.rpm" && wget -cO MariaDB-shared-10.1.{self.arch}.rpm "{self.url}/helper_files/mariadb-shared-10.1-kvm-rpm-{self.rpm_type}-{self.arch}.rpm"',
            ),
        ]
