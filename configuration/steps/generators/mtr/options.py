from dataclasses import dataclass

from configuration.steps.generators.base.options import Option

try:
    # breaking change introduced in python 3.11
    from enum import StrEnum
except ImportError:  # pragma: no cover
    from configuration.steps.generators.base.options import StrEnum


class MTR(StrEnum):
    # This class is used for type safety and preventing typos. Instead of
    # passing raw strings to create an MTR run command, generate the flag
    # list via an array of MTRFlags and their values.
    BIG_TEST = "big-test"
    CURSOR_PROTOCOL = "cursor-protocol"
    FORCE = "force"
    IN_MEMORY = "mem"
    MAX_SAVE_DATADIR = "max-save-datadir"
    MAX_SAVE_CORE = "max-save-core"
    MAX_TEST_FAIL = "max-test-fail"
    MYSQLD_ARGS = "mysqld"
    PARALLEL = "parallel"
    PREPARED_STATEMENT_PROTOCOL = "ps-protocol"
    RETRY = "retry"
    # NOTE: This option accepts a regex. The generator should be tested if
    # escaping regexes with space or ".
    SKIP_TEST = "skip-test"
    STORED_PROCEDURE_PROTOCOL = "sp-protocol"
    SUITE = "suite"
    VALGRIND = "valgrind"
    VERBOSE_RESTART = "verbose-restart"
    VIEW_PROTOCOL = "view-protocol"
    WITH_EMBEDDED = "embedded"
    VARDIR = "vardir"


# Extracted from ./mtr output manually before tests actually start.
# Should be updated when new specific suites need to be mentioned.
class SUITE(StrEnum):
    ARCHIVE = "archive"
    ATOMIC = "atomic"
    BINLOG = "binlog"
    BINLOG_ENCRYPTION = "binlog_encryption"
    COMAT_MSSQL = "compat/mssql"
    COMPAT_MAXDB = "compat/maxdb"
    COMPAT_ORACLE = "compat/oracle"
    CSV = "csv"
    DISKS = "disks"
    ENCRYPTION = "encryption"
    EVENTS = "events"
    FEDERATED = "federated"
    FUNCS_1 = "funcs_1"
    FUNCS_2 = "funcs_2"
    FUNC_TEST = "func_test"
    GALERA = "galera"
    GALERA_3NODES = "galera_3nodes"
    GALERA_3NODES_SR = "galera_3nodes_sr"
    GCOL = "gcol"
    HANDLER = "handler"
    HEAP = "heap"
    INNODB = "innodb"
    INNODB_FTS = "innodb_fts"
    INNODB_GIS = "innodb_gis"
    INNODB_I_S = "innodb_i_s"
    INNODB_ZIP = "innodb_zip"
    JSON = "json"
    MAIN = "main"
    MARIA = "maria"
    MARIABACKUP = "mariabackup"
    MERGE = "merge"
    METADATA_LOCK_INFO = "metadata_lock_info"
    MULTI_SOURCE = "multi_source"
    OPTIMIZER_UNFIXED_BUGS = "optimizer_unfixed_bugs"
    PARTS = "parts"
    PERFSCHEMA = "perfschema"
    PERIOD = "period"
    PLUGINS = "plugins"
    QUERY_RESPONSE_TIME = "query_response_time"
    ROLES = "roles"
    RPL = "rpl"
    SEQUENCE = "sequence"
    SPIDER = "spider"
    SPIDER_BG = "spider/bg"
    SPIDER_BUGFIX = "spider/bugfix"
    SPIDER_FEATURE = "spider/feature"
    SPIDER_REGRESSION_E1121 = "spider/regression/e1121"
    SPIDER_REGRESSION_E112122 = "spider/regression/e112122"
    SQL_DISCOVERY = "sql_discovery"
    SQL_SEQUENCE = "sql_sequence"
    STRESS = "stress"
    SYSSCHEMA = "sysschema"
    SYS_VARS = "sys_vars"
    TYPE_INET = "type_inet"
    TYPE_MYSQL_TIMESTAMP = "type_mysql_timestamp"
    TYPE_TEST = "type_test"
    TYPE_UUID = "type_uuid"
    UNIT = "unit"
    USER_VARIABLES = "user_variables"
    VCOL = "vcol"
    VERSIONING = "versioning"
    WSREP = "wsrep"


@dataclass
class TestSuiteCollection:
    suites: list[StrEnum]

    def __post_init__(self):
        assert self.suites
        self.suites = sorted(self.suites)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__str__()})"

    def __str__(self):
        res = ""
        for suite in self.suites:
            res += f"{suite.value},"
        return res[:-1]


class MTROption(Option):
    def as_cmd_arg(self) -> str:
        if isinstance(self.value, bool):
            if not self.value:
                return f"--no{self.name}"
            else:
                return f"--{self.name}"
        return f"--{self.name}={self.value}"
