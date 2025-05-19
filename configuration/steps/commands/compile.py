from enum import Enum
from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class MAKE(Enum):
    COMPILE = ""
    PACKAGE = "package"
    SOURCE = "package_source"


class CompileMakeCommand(Command):
    def __init__(
        self,
        option: MAKE,
        jobs: int,
        verbose: bool = False,
        workdir: PurePath = PurePath("."),
        output_sync: bool = True,
    ):
        self.verbose = verbose
        self.output_sync = output_sync
        if not isinstance(option, MAKE):
            raise ValueError(f"Invalid option: {option}")
        self.name = f"Make - {option.name.lower()}"

        super().__init__(name=self.name, workdir=workdir)

        self.command = util.Interpolate(
            f"make -j%(kw:jobs)s %(kw:output_sync)s %(kw:verbose)s {option.value}",
            jobs=jobs,
            verbose="VERBOSE=1" if self.verbose else "",
            output_sync="--output-sync=target" if self.output_sync else "",
        )

    def as_cmd_arg(self) -> list[str]:
        result = ["bash", "-ec", self.command]
        return result


class CompileCMakeCommand(Command):
    def __init__(
        self,
        jobs: int,
        builddir: str = ".",
        verbose: bool = False,
        workdir: PurePath = PurePath("."),
    ):
        self.verbose = verbose
        self.builddir = builddir
        self.jobs = jobs
        super().__init__(name="Compile", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "cmake",
            "--build",
            f"{self.builddir}",
            "--verbose" if self.verbose else "",
            "--parallel",
            f"{self.jobs}",
        ]


class CompileDebAutobake(Command):
    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Compile - deb autobake", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return ["debian/autobake-deb.sh"]


class InstallRPMFromProp(Command):
    def __init__(
        self,
        property_name: str,
        workdir: PurePath = PurePath("."),
    ):
        name = "Install RPM Packages"
        self.property_name = property_name
        super().__init__(name=name, workdir=workdir, user="root")

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-ec",
            util.Interpolate(
                f"""
                    yum -y --nogpgcheck install %(kw:packages)s

                    if [ -d "/usr/share/mysql-test" ]; then
                        ln -s /usr/share/mysql-test /usr/share/mariadb-test
                    fi
                    """,
                packages=util.Property(self.property_name),
            ),
        ]
        return result
