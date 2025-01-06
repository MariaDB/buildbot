from enum import StrEnum


# Flag names use UPPER_CASE
class CMAKE(StrEnum):
    """
    Explicitly enumerates valid CMake flags to enforce type safety
    and avoid typos in flag names.
    """

    AR = "AR"
    BUILD_TYPE = "BUILD_TYPE"
    CXX_COMPILER = "CXX_COMPILER"
    CXX_FLAGS = "CXX_FLAGS"
    C_COMPILER = "C_COMPILER"
    C_FLAGS = "C_FLAGS"
    C_COMPILER_LAUNCHER = "C_COMPILER_LAUNCHER"
    CXX_COMPILER_LAUNCHER = "CXX_COMPILER_LAUNCHER"
    INSTALL_PREFIX = "INSTALL_PREFIX"
    LIBRARY_PATH = "LIBRARY_PATH"

    def __str__(self):
        return f"CMAKE_{self.value}"


class PLUGIN(StrEnum):
    """
    Enumerates valid plugin options for MariaDB's CMake configuration.
    """

    ARCHIVE_STORAGE_ENGINE = "ARCHIVE"
    CONNECT_STORAGE_ENGINE = "CONNECT"
    ROCKSDB_STORAGE_ENGINE = "ROCKSDB"
    TOKUDB_STORAGE_ENGINE = "TOKUDB"

    def __str__(self):
        return f"PLUGIN_{self.value}"


class WITH(StrEnum):
    """
    Enumerates valid options for MariaDB's CMake configuration. Each
    option starts with WITH_.
    """

    ASAN = "ASAN"
    DBUG_TRACE = "DBUG_TRACE"
    EMBEDDED_SERVER = "EMBEDDED_SERVER"
    JEMALLOC = "JEMALLOC"
    SAFEMALLOC = "SAFEMALLOC"
    UBSAN = "UBSAN"
    UNIT_TESTS = "UNIT_TESTS"
    VALGRIND = "VALGRIND"

    def __str__(self):
        return f"WITH_{self.value}"


class OTHER(StrEnum):
    """
    Enumerates other valid options for MariaDB's
    """

    BUILD_CONFIG = "BUILD_CONFIG"


# Flag values use CapitalCase
class BuildType(StrEnum):
    """
    Enumerates build types for CMake.
    """

    RELEASE = "Release"
    DEBUG = "Debug"
    RELWITHDEBUG = "RelWithDebInfo"


class BuildConfig(StrEnum):
    """
    Used for -DBUILD_CONFIG=<value> of cmake.
    Enumerates build configurations for MariaDB's CMake.
    """

    MYSQL_RELEASE = "mysql_release"


class CMakeOption:
    """
    Represents a CMake option in the form `-D<name>=<value>`.
    """

    @staticmethod
    def _quote_value(value: str):
        """
        Quote the value if it contains spaces or special characters.
        """
        if " " in value or '"' in value:
            return f'"{value.replace('"', '\\\"')}"'
        return value

    def __init__(self, name: StrEnum, value: str | bool):
        assert isinstance(name, StrEnum)
        assert isinstance(value, str) or isinstance(value, bool)
        self.name = str(name)
        if isinstance(value, bool):
            self.value = "ON" if value else "OFF"
        elif isinstance(value, str):
            self.value = value
        # Quote if necessary.
        self.value = self._quote_value(self.value)

    def as_cmd_arg(self) -> str:
        return f"-D{self.name}={self.value}"

    def __str__(self) -> str:
        return self.as_cmd_arg()

    def __repr__(self) -> str:
        return f"CMakeOption({self.name}, {self.value})"
