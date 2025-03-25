from typing import Iterable

from ..base.generator import BaseGenerator
from .compilers import CompilerCommand
from .options import CMAKE, OTHER, BuildConfig, CMakeOption


class CMakeGenerator(BaseGenerator):
    """
    Generates a CMake command with specified flags.
    """

    def __init__(self, flags: Iterable[CMakeOption], source_path: str = "."):
        """
        Initializes the CMakeGenerator with an optional list of flags.

        Args:
            flags: An iterable of CMakeFlag objects.
            source_path: The source path to the base CMakeLists.txt file.
                         Default path is "in source build".
        """
        super().__init__(base_cmd=["cmake", source_path], flags=flags)

    def set_compiler(self, compiler: CompilerCommand):
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

    def use_ccache(self):
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
