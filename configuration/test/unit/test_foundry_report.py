"""The dispatcher's status report, from the files the package builds write."""

import json
import os
import tempfile
import unittest

from configuration.steps.commands.scripts import foundry_report as report

PLUGINS = ["broken", "uninstallable", "no_tests", "failing", "passing"]
DEB = "foundry-amd64-debian-12-deb-autobake"
ARM = "foundry-aarch64-debian-12-deb-autobake"
BINTAR = "foundry-amd64-centos-7-bintar"
CI_ONLY = "foundry-amd64-debian-13-deb-autobake"
VERSIONS = {
    "11.4": {
        "foundry_11_4_scheduler": [DEB, ARM, BINTAR],
        "foundry_11_4_ci_only_scheduler": [CI_ONLY],
    },
    "11.8": {"foundry_11_8_scheduler": [DEB]},
    "12.3": {"foundry_12_3_scheduler": [DEB]},
}
MIRROR_RUN = ["foundry_11_4_scheduler", "foundry_11_8_scheduler"]
# 11.4 from CI tarball 1234, 11.8 from the mirrors.
SOURCES = {"11.4": "1234", "11.8": "mirror"}
CI_URL = "https://ci.mariadb.org"


def _write(directory, name, text):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name), "w") as f:
        f.write(text)


def _statuses(stages):
    return [stages[s]["status"] for s in ("build", "install", "mtr")]


class TestFoundryReport(unittest.TestCase):
    def setUp(self):
        self.run_dir = tempfile.mkdtemp()
        deb = self._dir("11.4", DEB)
        _write(
            deb,
            "build",
            "FAIL broken build 2\n"
            "PASS uninstallable u.deb\n"
            "PASS no_tests n.deb\n"
            "PASS failing f.deb\n"
            "PASS passing p.deb\n",
        )
        _write(
            deb,
            "install",
            "uninstallable fail\nno_tests pass\nfailing pass\npassing pass\n",
        )
        _write(deb, "suites", "failing failing_suite\npassing passing_suite\n")
        _write(
            deb,
            "mtr",
            "Completed: Failed 1/3 tests, 66.67% were successful.\n"
            "Failing test(s): failing_suite.t1 failing_suite.t2 'innodb'\n",
        )
        bintar = self._dir("11.4", BINTAR)
        _write(bintar, "build", "PASS passing p.tar.gz\n")
        _write(bintar, "suites", "passing passing_suite\n")
        _write(bintar, "mtr", "Completed: All 2 tests were successful.\n")

    def _dir(self, version, builder):
        # The build's status files.
        return os.path.join(self.run_dir, version, builder, "status")

    def _status(self, triggered=MIRROR_RUN):
        return report.run_status(self.run_dir, VERSIONS, triggered, PLUGINS, SOURCES)

    def _builders(self, version, triggered=MIRROR_RUN):
        return self._status(triggered)[version]["builders"]

    def test_deb_platform(self):
        deb = self._builders("11.4")[DEB]
        self.assertEqual(
            deb["broken"]["build"], {"status": "fail", "detail": "build 2"}
        )
        self.assertEqual(_statuses(deb["broken"]), ["fail", "not run", "not run"])
        self.assertEqual(_statuses(deb["uninstallable"]), ["pass", "fail", "not run"])
        self.assertEqual(_statuses(deb["no_tests"]), ["pass", "pass", "no suites"])
        self.assertEqual(
            deb["failing"]["mtr"],
            {
                "status": "fail",
                "failed_tests": ["failing_suite.t1", "failing_suite.t2 'innodb'"],
            },
        )
        self.assertEqual(_statuses(deb["passing"]), ["pass", "pass", "pass"])

    def test_bintar_platform(self):
        bintar = self._builders("11.4")[BINTAR]
        self.assertEqual(_statuses(bintar["passing"]), ["pass", "n/a", "pass"])
        self.assertEqual(
            bintar["broken"]["build"]["detail"], "not reported by run.cmake"
        )

    def test_versions_and_builders(self):
        status = self._status()
        # Triggered, but its builders failed before writing anything.
        self.assertIsNone(status["11.4"]["builders"][ARM])
        self.assertEqual(status["11.8"]["builders"], {DEB: None})
        # Not fired: the ci_only Triggerable on a mirror run, and 12.3.
        self.assertNotIn(CI_ONLY, status["11.4"]["builders"])
        self.assertIsNone(status["12.3"])

    def test_server_source(self):
        status = self._status()
        self.assertEqual(status["11.4"]["tarbuildnum"], "1234")
        self.assertIsNone(status["11.8"]["tarbuildnum"])

    def test_ci_only_builder_that_failed_early(self):
        builders = self._builders(
            "11.4", MIRROR_RUN + ["foundry_11_4_ci_only_scheduler"]
        )
        self.assertIsNone(builders[CI_ONLY])

    def test_builder_failed_before_each_stage(self):
        def stages(files):
            directory = self._dir("11.8", DEB)
            for name, text in files.items():
                _write(directory, name, text)
            return _statuses(self._builders("11.8")[DEB]["passing"])

        os.makedirs(self._dir("11.8", DEB))
        self.assertEqual(stages({}), ["builder failed", "not run", "not run"])
        self.assertEqual(
            stages({"build": "PASS passing p.deb\n"}),
            ["pass", "builder failed", "not run"],
        )
        self.assertEqual(
            stages({"install": "passing pass\n"}), ["pass", "pass", "builder failed"]
        )
        self.assertEqual(
            stages({"suites": "passing s\n"}), ["pass", "pass", "builder failed"]
        )
        self.assertEqual(stages({"mtr": ""}), ["pass", "pass", "builder failed"])

    def test_version_overview(self):
        passing = {"p": {s: {"status": "pass"} for s in ("build", "install", "mtr")}}
        untested = {"p": {**passing["p"], "mtr": {"status": "no suites"}}}
        failing = {"p": {**passing["p"], "mtr": {"status": "fail"}}}
        self.assertFalse(report.has_failures(passing))
        self.assertFalse(report.has_failures(untested))
        self.assertTrue(report.has_failures(failing))
        self.assertTrue(report.has_failures(None))  # no status
        self.assertIn("no failures on 1 builder<", report.overview({"a": passing}))
        self.assertIn(
            "failures on 2 of 3 builders<",
            report.overview({"a": passing, "b": failing, "c": None}),
        )

    def test_main_writes_the_page(self):
        report.main(
            self.run_dir,
            json.dumps(VERSIONS),
            " ".join(MIRROR_RUN),
            " ".join(PLUGINS),
            "abc",
            "11.4=1234 11.4=1234 11.8=mirror",
            CI_URL,
        )
        with open(os.path.join(self.run_dir, "status.html")) as f:
            page = f.read()
        self.assertIn("MariaDB 11.4", page)
        self.assertIn(
            'CI tarball <a href="https://ci.mariadb.org/1234/">1234</a>', page
        )
        self.assertIn("Server packages: MariaDB Server mirrors", page)  # 11.8
        # Each builder links to its own directory.
        self.assertIn(f'<caption><a href="11.4/{DEB}/">{DEB}</a></caption>', page)
        self.assertIn("failing_suite.t2 &#x27;innodb&#x27;", page)
        self.assertIn("No status", page)
        self.assertIn("Not triggered in this run", page)
        self.assertIn("What each status means", page)
        for status, meaning in report.LEGEND.items():
            self.assertIn(f"{status}</span></td><td>", page)
            self.assertTrue(meaning)
        self.assertNotIn("passing_suite.", page)  # passing tests aren't listed
        # Versions are sections, collapsed until opened, with their result.
        self.assertEqual(page.count('<details class="version">'), 2)
        self.assertNotIn("<details open", page)
        self.assertIn(
            '<summary>MariaDB 11.4 <span class="fail">failures on 3 of 3 builders',
            page,
        )
        self.assertIn('<p class="version">MariaDB 12.3 ', page)  # not triggered
        # What the plugin and builder filters work on.
        for plugin in PLUGINS:
            self.assertIn(f'<option value="{plugin}">{plugin}</option>', page)
            self.assertIn(f'<tr data-plugin="{plugin}">', page)
        self.assertEqual(page.count(f'<table data-builder="{DEB}">'), 2)
        self.assertIn('id="builder"', page)
        self.assertIn('id="toggle"', page)
        with open(os.path.join(self.run_dir, "status.json")) as f:
            self.assertEqual(json.load(f), self._status())


if __name__ == "__main__":
    unittest.main()
