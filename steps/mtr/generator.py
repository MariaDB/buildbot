from typing import Iterable

from ..base.generator import BaseGenerator
from .options import MTR, MTROption, TestSuiteCollection


class MTRGenerator(BaseGenerator):
    def __init__(self, flags: Iterable[MTROption]):
        super().__init__(
            base_cmd=["perl", "mariadb-test-run.pl"], flags=flags, allow_duplicates=True
        )

    def set_test_suites(self, suites: TestSuiteCollection):
        self.append_flags([MTROption(MTR.SUITE, str(suites))])
