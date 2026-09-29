"""How the Foundry build step reads run.cmake's summary."""

import unittest

from buildbot.process.results import FAILURE, SUCCESS, WARNINGS
from configuration.steps.commands.foundry import FoundrySummary

# The tail of a real run.cmake run, as the step's stdout carries it.
_OUTPUT = """\
-- Build params: -DRPM=1
-- Parallel jobs: 1
-- Building tidesql
-- Building broken
-- Building empty
-- ---------------- Foundry summary ----------------
-- FOUNDRY-RESULT: PASS tidesql MariaDB-plugin-tidesdb-5.0.0-1.el9.x86_64.rpm MariaDB-plugin-tidesdb-debuginfo-5.0.0-1.el9.x86_64.rpm
-- FOUNDRY-RESULT: FAIL broken build 2
-- FOUNDRY-RESULT: FAIL empty package No packages found
-- FOUNDRY-SUMMARY: 2 of 3 plugins failed
"""


def _summary(output: str) -> FoundrySummary:
    # Split on "\n" only, like LogLineObserver, so a "\r" reaches feed().
    summary = FoundrySummary()
    for line in output.split("\n"):
        summary.feed(line)
    return summary


class TestFoundrySummary(unittest.TestCase):
    def test_reads_each_plugin_line(self):
        summary = _summary(_OUTPUT)
        self.assertEqual(summary.built, ["tidesql"])
        self.assertEqual(
            summary.failures,
            {"broken": "build: 2", "empty": "package: No packages found"},
        )
        self.assertTrue(summary.complete)

    def test_every_plugin_built(self):
        summary = _summary(
            "-- FOUNDRY-RESULT: PASS a a.deb\n"
            "-- FOUNDRY-RESULT: PASS b b.deb b-dbgsym.deb\n"
            "-- FOUNDRY-SUMMARY: 0 of 2 plugins failed\n"
        )
        self.assertEqual(
            summary.evaluate(["a", "b"], command_ok=True),
            (SUCCESS, ["a", "b"], {}, "built 2 of 2 plugins"),
        )

    def test_some_plugins_built(self):
        """A warning; flunkOnWarnings fails the build."""
        result, built, failures, description = _summary(_OUTPUT).evaluate(
            ["tidesql", "broken", "empty"], command_ok=False
        )
        self.assertEqual(result, WARNINGS)
        self.assertEqual(built, ["tidesql"])
        self.assertEqual(list(failures), ["broken", "empty"])
        self.assertEqual(
            description,
            "built 1 of 3 plugins; failed: broken (build: 2), "
            "empty (package: No packages found)",
        )

    def test_no_plugin_built(self):
        summary = _summary(
            "-- FOUNDRY-RESULT: FAIL a configure 1\n"
            "-- FOUNDRY-SUMMARY: 1 of 1 plugins failed\n"
        )
        self.assertEqual(
            summary.evaluate(["a"], command_ok=False),
            (
                FAILURE,
                [],
                {"a": "configure: 1"},
                "built 0 of 1 plugins; failed: a (configure: 1)",
            ),
        )

    def test_no_summary(self):
        """run.cmake stopped early or never ran."""
        summary = _summary("-- Building a\nCMake Error: something\n")
        result, built, failures, description = summary.evaluate(["a"], command_ok=False)
        self.assertEqual(result, FAILURE)
        self.assertEqual(built, [])
        self.assertEqual(failures, {"a": "not reported by run.cmake"})
        self.assertEqual(description, "run.cmake printed no summary")

    def test_requested_plugin_missing_from_the_summary(self):
        """run.cmake silently skips names with a dot."""
        summary = _summary(
            "-- FOUNDRY-RESULT: PASS a a.rpm\n"
            "-- FOUNDRY-SUMMARY: 0 of 1 plugins failed\n"
        )
        result, built, failures, _ = summary.evaluate(["a", "b.c"], command_ok=True)
        self.assertEqual(result, WARNINGS)
        self.assertEqual(built, ["a"])
        self.assertEqual(failures, {"b.c": "not reported by run.cmake"})

    def test_all_built_but_cmake_failed(self):
        summary = _summary(
            "-- FOUNDRY-RESULT: PASS a a.rpm\n"
            "-- FOUNDRY-SUMMARY: 0 of 1 plugins failed\n"
        )
        result, built, _, description = summary.evaluate(["a"], command_ok=False)
        self.assertEqual(result, FAILURE)
        self.assertEqual(built, ["a"])
        self.assertEqual(description, "built 1 of 1 plugins, but cmake failed")

    def test_ignores_lines_that_only_mention_the_markers(self):
        """bash -x traces, and plugins' own "-- " lines."""
        summary = _summary(
            "+ echo '-- FOUNDRY-RESULT: PASS fake fake.rpm'\n"
            "  -- FOUNDRY-RESULT: PASS indented x.rpm\n"
            "-- FOUNDRY-RESULTS: PASS typo x.rpm\n"
            "-- FOUNDRY-RESULT: PASS\n"
            "-- Configuring done\n"
        )
        self.assertEqual(summary.built, [])
        self.assertEqual(summary.failures, {})
        self.assertFalse(summary.complete)

    def test_tolerates_trailing_whitespace(self):
        summary = _summary(
            "-- FOUNDRY-RESULT: PASS a a.rpm \r\n-- FOUNDRY-SUMMARY: 0 of 1 plugins failed\r\n"
        )
        self.assertEqual(summary.built, ["a"])
        self.assertTrue(summary.complete)


if __name__ == "__main__":
    unittest.main()
