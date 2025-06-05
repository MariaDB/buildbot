from pathlib import PurePath

from configuration.steps.commands.base import Command
from configuration.steps.generators.cmake.generator import CMakeGenerator


class ConfigureMariaDBCMake(Command):
    """
    A command to configure MariaDB using CMake.
    This command generates the necessary build files for MariaDB
    based on the provided CMake generator.
    Attributes:
        name (str): The name of the command.
        cmake_generator (CMakeGenerator): The CMake generator to use for configuration.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        name: str,
        cmake_generator: CMakeGenerator,
        workdir: PurePath = PurePath("."),
    ):
        self.cmake_generator = cmake_generator
        super().__init__(name=f"Configure - {name}", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return self.cmake_generator.generate()
