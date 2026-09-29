"""How the Foundry steps find the MTR suites in the plugins' package files."""

import os
import subprocess
import tempfile
import unittest

from configuration.steps.commands.foundry import BUILT_PLUGINS_ENV, _print_suites

# The files of each plugin's package, as rpm -qlp lists them: a suite with its
# tests in t/, one with its tests in the suite directory, and no suite.
_FILES = {
    "spider": """\
/usr/lib64/mysql/plugin/ha_spider.so
/usr/share/mariadb-test/plugin/spider/spider/r/basic.result
/usr/share/mariadb-test/plugin/spider/spider/t/basic.test
/usr/share/mariadb-test/plugin/spider/spider/t/other.test
""",
    "levenshtein": """\
/etc/my.cnf.d/levenshtein.cnf
/usr/lib/.build-id
/usr/lib/.build-id/c7
/usr/lib/.build-id/c7/550acdc8b03dafd1d69b9861dc45f5493af0e8
/usr/lib64/mysql/plugin/levenshtein.so
/usr/share/mariadb-test/plugin/levenshtein
/usr/share/mariadb-test/plugin/levenshtein/levenshtein
/usr/share/mariadb-test/plugin/levenshtein/levenshtein/basic.result
/usr/share/mariadb-test/plugin/levenshtein/levenshtein/basic.test
/usr/share/mariadb-test/plugin/levenshtein/levenshtein/suite.opt
""",
    "no_tests": "/usr/lib64/mysql/plugin/no_tests.so\n",
}


class TestFoundrySuites(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = tmp.name
        for plugin, files in _FILES.items():
            os.mkdir(os.path.join(self.workdir, f"{plugin}.build"))
            with open(os.path.join(self.workdir, f"{plugin}.build", "files"), "w") as f:
                f.write(files)

    def _print_suites(self):
        # The shell the suite steps run, with cat for listing a package's files.
        shell = _print_suites('"$p.build"/files', 'cat "$f"')
        return subprocess.run(
            ["bash", "-c", f"set -euo pipefail\n{shell}"],
            cwd=self.workdir,
            env={**os.environ, BUILT_PLUGINS_ENV: " ".join(_FILES)},
            capture_output=True,
            text=True,
            check=True,
        )

    def test_suites_in_t_or_in_the_suite_directory(self):
        result = self._print_suites()
        self.assertEqual(result.stdout, "spider,levenshtein\n")
        self.assertIn("no_tests has no MTR suite", result.stderr)


if __name__ == "__main__":
    unittest.main()
