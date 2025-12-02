from typing import Union

from configuration.steps.generators.base.generator import Option

try:
    # breaking change introduced in python 3.11
    from enum import StrEnum  # pyright: ignore
except ImportError:  # pragma: no cover
    from configuration.steps.generators.base.options import StrEnum  # pyright: ignore


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
    EXE_LINKER_FLAGS = "EXE_LINKER_FLAGS"
    EXPORT_COMPILE_COMMANDS = "EXPORT_COMPILE_COMMANDS"
    INSTALL_PREFIX = "INSTALL_PREFIX"
    LIBRARY_PATH = "LIBRARY_PATH"
    MODULE_LINKER_FLAGS = "MODULE_LINKER_FLAGS"

    def __str__(self):
        return f"CMAKE_{self.value}"


class CMAKEWARN(StrEnum):
    DEVELOPER_WARNINGS = "dev"
    DEPRECATED_WARNINGS = "deprecated"
    WARNINGS_AS_ERRORS = "error"

    def __str__(self):
        return self.value


class CMAKEDEBUG(StrEnum):
    TRACE = "trace"
    TRACE_EXPAND = "trace-expand"
    DEBUG_OUTPUT = "debug-output"
    DEBUG_FIND = "debug-find"

    def __str__(self):
        return self.value


class PLUGIN(StrEnum):
    """
    Enumerates valid plugin options for MariaDB's CMake configuration.
    """

    ARCHIVE_STORAGE_ENGINE = "ARCHIVE"
    COLUMNSTORE_STORAGE_ENGINE = "COLUMNSTORE"
    CONNECT_STORAGE_ENGINE = "CONNECT"
    FEDERATED_STORAGE_ENGINE = "FEDERATED"
    FEDERATEDX_STORAGE_ENGINE = "FEDERATEDX"
    FEEDBACK = "FEEDBACK"
    INNOBASE = "INNOBASE"
    ROCKSDB_STORAGE_ENGINE = "ROCKSDB"
    MROONGA_STORAGE_ENGINE = "MROONGA"
    OQGRAPH_STORAGE_ENGINE = "OQGRAPH"
    PARTITION = "PARTITION"
    PERFSCHEMA_FEATURE = "PERFSCHEMA"
    SEQUENCE = "SEQUENCE"
    SPHINX_STORAGE_ENGINE = "SPHINX"
    SPIDER_STORAGE_ENGINE = "SPIDER"
    THREAD_POOL_INFO = "THREAD_POOL_INFO"
    TOKUDB_STORAGE_ENGINE = "TOKUDB"
    USER_VARIABLES = "USER_VARIABLES"

    def __str__(self):
        return f"PLUGIN_{self.value}"


class WITH(StrEnum):
    """
    Enumerates valid options for MariaDB's CMake configuration. Each
    option starts with WITH_.
    """

    ASAN = "ASAN"
    ASAN_SCOPED = "ASAN_SCOPED"
    DBUG_TRACE = "DBUG_TRACE"
    EMBEDDED_SERVER = "EMBEDDED_SERVER"
    EXTRA_CHARSETS = "EXTRA_CHARSETS"
    JEMALLOC = "JEMALLOC"
    MSAN = "MSAN"
    NONE = "NONE"
    SAFEMALLOC = "SAFEMALLOC"
    SSL = "SSL"
    SYSTEMD = "SYSTEMD"
    UBSAN = "UBSAN"
    UNIT_TESTS = "UNIT_TESTS"
    VALGRIND = "VALGRIND"
    WSREP = "WSREP"
    ZLIB = "ZLIB"

    def __str__(self):
        return f"WITH_{self.value}"


class WITHOUT(StrEnum):
    """
    Enumerates valid options for MariaDB's CMake configuration. Each
    option starts with WITHOUT_.
    """

    SERVER = "SERVER"
    PACKED_SORT_KEYS = "PACKED_SORT_KEYS"

    def __str__(self):
        return f"WITHOUT_{self.value}"


class OTHER(StrEnum):
    """
    Enumerates other valid options for MariaDB's
    """

    BUILD_CONFIG = "BUILD_CONFIG"
    ENABLED_PROFILING = "ENABLED_PROFILING"
    RPM = "RPM"


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


class CMakeVariableOption(Option):
    """
    Represents a `-DNAME=VALUE` variable option
    """

    def __init__(self, name: StrEnum, value: Union[str, bool]):
        if isinstance(value, bool):
            value = "ON" if value else "OFF"
        super().__init__(name, value)

    def as_cmd_arg(self) -> str:
        return f"-D{self.name}={self.value}"


class CMakePluginOption(CMakeVariableOption):
    def __init__(self, name: PLUGIN, value: bool):
        assert isinstance(value, bool)
        super().__init__(name, "YES" if value else "NO")


class CMakeFlagOption(Option):
    """
    Represents a flag-like option (e.g., --trace, --trace-expand).
    """

    def __init__(self, name: StrEnum, value: bool):
        assert isinstance(value, bool)
        flag = f"--{name}" if value else ""
        super().__init__(name, flag)

    def as_cmd_arg(self) -> str:
        return str(self.value)


class CMakeWarnOption(Option):
    """
    Represents a -W option (e.g., -Wno-dev, -Wdeprecated).
    """

    def __init__(self, name: StrEnum, value: bool):
        assert isinstance(value, bool)
        flag = f"-W{'' if value else 'no-'}{name}"
        super().__init__(name, flag)

    def as_cmd_arg(self) -> str:
        return str(self.value)


class CMakeOption:
    """
    Factory class to create CMake options based on the type of the input object.
    """

    HANDLERS = (
        (
            (
                CMAKE,
                WITH,
                WITHOUT,
                OTHER,
                BuildType,
                BuildConfig,
            ),
            CMakeVariableOption,
        ),
        (
            (CMAKEDEBUG,),
            CMakeFlagOption,
        ),
        (
            (CMAKEWARN,),
            CMakeWarnOption,
        ),
        (
            (PLUGIN,),
            CMakePluginOption,
        ),
    )

    def __new__(cls, obj: StrEnum, value: Union[str, bool]) -> Option:
        for base_classes, handler_class in cls.HANDLERS:
            if isinstance(obj, base_classes):
                return handler_class(obj, value)  # pyright: ignore
        raise ValueError(
            f"No handler found for object of type {type(obj)}. Cannot create a CMake option."
        )
