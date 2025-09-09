from enum import Enum
from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class MAKE(Enum):
    """
    Enum representing different Make options for compilation or packaging.
    This enum defines the available options for Make commands,
    such as compiling, packaging, or generating source packages.
    Attributes:
        COMPILE (str): The option for compiling the project.
        PACKAGE (str): The option for packaging the project.
        SOURCE (str): The option for generating source packages.
    """

    COMPILE = ""
    PACKAGE = "package"
    PACKAGE_SOURCE = "package_source"


class CompileMakeCommand(Command):
    """
    A command to compile or package a project using Make.
    This command executes the Make build system with specified options,
    such as the number of jobs, verbosity, and output synchronization.
    Attributes:
        option (MAKE): The Make option to use (e.g., COMPILE, PACKAGE, SOURCE).
        jobs (int): The number of parallel jobs to run.
        verbose (bool): Whether to enable verbose output.
        workdir (PurePath): The working directory for the command.
        output_sync (bool): Whether to synchronize output with the target.
    """

    def __init__(
        self,
        option: MAKE,
        jobs: int,
        verbose: bool = False,
        workdir: PurePath = PurePath("."),
        output_sync: bool = False,
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
        result = ["bash", "-exc", self.command]
        return result


class CompileCMakeCommand(Command):
    """
    A command to compile a project using CMake.
    This command builds the project in the specified build directory
    with the given number of jobs and verbosity.
    Attributes:
        jobs (int): The number of parallel jobs to run.
        builddir (str): The directory where the build files are located.
        verbose (bool): Whether to enable verbose output.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        jobs: int,
        builddir: str = ".",
        verbose: bool = False,
        workdir: PurePath = PurePath("."),
        targets: list[str] = None,
    ):
        self.verbose = verbose
        self.builddir = builddir
        self.jobs = jobs
        self.targets = targets
        super().__init__(name="Compile", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        r_list = [
            "cmake",
            "--build",
            f"{self.builddir}",
            "--parallel",
            f"{self.jobs}",
        ]
        if self.verbose:
            r_list.append("--verbose")
        if self.targets:
            r_list.append("--targets")
            r_list.append(self.targets)
        return r_list


class CompileDebAutobake(Command):
    """
    A command to compile Debian packages using the autobake script.
    This command executes the autobake script located in the debian directory.
    Attributes:
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Compile - deb autobake", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return ["bash", "-exc", "debian/autobake-deb.sh"]


class InstallRPMFromProp(Command):
    """
    This class is used to install RPM packages from a property.
    It reads the list of packages from a specified property
    and installs them using the yum package manager.
    Attributes:
        property_name (str): The name of the property containing the list of packages.
        workdir (PurePath): The working directory for the command.
    """

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
            "-exc",
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
