from typing import Iterable

from configuration.steps.generators.base.generator import BaseGenerator
from configuration.steps.generators.cmake.compilers import CompilerCommand
from configuration.steps.generators.cmake.options import (
    CMAKE,
    OTHER,
    BuildConfig,
    CMakeOption,
)


class CMakeGenerator(BaseGenerator):
    """
    Generates a CMake command with specified flags.
    """

    def __init__(
        self,
        flags: Iterable[CMakeOption],
        use_ccache: bool = False,
        compiler: CompilerCommand = None,
        source_path: str = ".",
        builddir: str = None,
    ):
        """
        Initializes the CMakeGenerator with an optional list of flags.

        Args:
            flags: An iterable of CMakeFlag objects.
            use_ccache: A boolean flag to enable ccache.
            compiler: An instance of CompilerCommand if you want to set it explicitly.
            source_path: The source path to the base CMakeLists.txt file.
                         Default path is "in source build".
            builddir: The path of the build directory. Default is None.
        """
        base_command = ["cmake", "-S", source_path]
        if builddir:
            base_command += ["-B", builddir]
        super().__init__(base_cmd=base_command, flags=flags)

        if use_ccache:
            self._use_ccache()

        if compiler:
            self._set_compiler(compiler)

    def _set_compiler(self, compiler: CompilerCommand):
        """
        Sets the compiler options for C and C++ compilers.

        Args:
            compiler: An instance of CompilerCommand.
        """
        assert isinstance(compiler, CompilerCommand)
        self.append_flags(
            [
                CMakeOption(CMAKE.C_COMPILER, compiler.cc),
                CMakeOption(CMAKE.CXX_COMPILER, compiler.cxx),
            ]
        )

    def _use_ccache(self):
        """
        Configures CMake to use ccache for faster builds.
        """
        self.append_flags(
            [
                CMakeOption(CMAKE.C_COMPILER_LAUNCHER, "ccache"),
                CMakeOption(CMAKE.CXX_COMPILER_LAUNCHER, "ccache"),
            ]
        )

    # TODO(cvicentiu) write unit test.
    def set_build_config(self, config: BuildConfig):
        """
        Set the build config flag. This is separate because of it being a
        "one-off" special flag.
        """
        self.append_flags([CMakeOption(OTHER.BUILD_CONFIG, config)])
