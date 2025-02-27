from buildbot import interfaces, steps

from .base import Command
from .cmake.options import CMakeOption, BuildType, CMAKE
from .cmake.compilers import CompilerCommand
from .cmake.generator import CMakeGenerator


class ConfigureMariaDBCMake(Command):
    def __init__(self,
                 name: str,
                 cmake_generator: CMakeGenerator,
                 workdir: str = ''):
        self.cmake_generator = cmake_generator
        super().__init__(name=f'Configure MariaDB Server - {name}',
                         workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return self.cmake_generator.generate()


def simple_debug_conf(compiler: CompilerCommand = None,
                      use_ccache: bool = False,
                      workdir: str = '') -> ConfigureMariaDBCMake:
    return ConfigureMariaDBCMake(
        name='Debug Build',
        cmake_generator=CMakeGenerator(
            compiler=compiler,
            use_ccache=use_ccache,
            flags=[
                CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG),
            ]),
        workdir=workdir)
