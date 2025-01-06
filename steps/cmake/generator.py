from typing import Iterable

from .compilers import CompilerCommand
from .options import CMAKE, OTHER, BuildConfig, CMakeOption


class DuplicateFlagException(Exception):
    def __init__(self, flag_name: str, existing_value: str, new_value: str):
        super().__init__(
            f"Duplicate flag detected: {flag_name}"
            f"(existing: {existing_value}, new: {new_value})"
        )
        super().__init__(f"Duplicate flag detected: {flag_name}")


class CMakeGenerator:
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
        self.flags: dict[str, CMakeOption] = {}
        self.source_path = source_path
        self.append_flags(flags)

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

    def append_flags(self, flags: Iterable[CMakeOption]):
        """
        Appends new flags to the generator.

        Raises:
            DuplicateFlagException: If a flag with the same name already
                                    exists.
        """
        for flag in flags:
            # Do not allow duplicate flags being set.
            # Flags should only be set once to avoid confusion about them
            # being overwritten.
            if flag.name in self.flags:
                existing_flag = self.flags[flag.name]
                raise DuplicateFlagException(flag.name, existing_flag.value, flag.value)
            self.flags[flag.name] = flag

    def generate(self) -> list[str]:
        """
        Generates the CMake command as a list of strings.
        """
        result = ["cmake", self.source_path]
        for flag in sorted(list(self.flags.values()), key=lambda x: x.name):
            result.append(flag.as_cmd_arg())
        return result
