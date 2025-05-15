from configuration.steps.commands.base import Command
from configuration.steps.generators.cmake.generator import CMakeGenerator


class ConfigureMariaDBCMake(Command):
    def __init__(self, name: str, cmake_generator: CMakeGenerator, workdir: str = ""):
        self.cmake_generator = cmake_generator
        super().__init__(name=f"Configure - {name}", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return self.cmake_generator.generate()
