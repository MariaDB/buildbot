import unittest

from configuration.steps.generators.mtr.generator import MTRGenerator
from configuration.steps.generators.mtr.options import (
    MTR,
    SUITE,
    MTROption,
    TestSuiteCollection,
)


class TestMTRGenerator(unittest.TestCase):
    def test_initialization_with_flags(self):
        """Test that the generator initializes with provided flags."""
        flags = [
            MTROption(MTR.FORCE, True),
            MTROption(MTR.MAX_TEST_FAIL, 5),
            MTROption(MTR.VALGRIND, True),
            MTROption(MTR.PARALLEL, 4),
        ]
        generator = MTRGenerator(flags=flags)
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "perl",
                "mariadb-test-run.pl",
                "--force",
                "--max-test-fail=5",
                "--parallel=4",
                "--valgrind",
            ],
        )

    def test_append_flags_successful(self):
        """
        Test that flags are appended successfully.
        """
        generator = MTRGenerator(flags=[])
        generator.append_flags(
            [
                MTROption(MTR.VERBOSE_RESTART, True),
                MTROption(MTR.WITH_EMBEDDED, True),
            ]
        )
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "perl",
                "mariadb-test-run.pl",
                "--embedded",
                "--verbose-restart",
            ],
        )

    def test_append_flags_duplicate_allow(self):
        """
        Test that appending a duplicate flag does not raise an exception.
        """
        flags = [MTROption(MTR.MAX_TEST_FAIL, 10)]
        generator = MTRGenerator(flags=flags)
        duplicate_flag = MTROption(MTR.MAX_TEST_FAIL, 5)
        generator.append_flags([duplicate_flag])
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "perl",
                "mariadb-test-run.pl",
                # Stable sort, by name, first in, first out if name equal.
                "--max-test-fail=10",
                "--max-test-fail=5",
            ],
        )

    def test_generate_with_no_flags(self):
        """
        Test that generate produces only the 'perl mariadb-test-run.pl' command if no flags are set.
        """
        generator = MTRGenerator(flags=[])
        command = generator.generate()
        self.assertEqual(command, ["perl", "mariadb-test-run.pl"])

    def test_set_test_suites(self):
        """
        Test that setting test suites adds the correct suite flag.
        """
        generator = MTRGenerator(
            flags=[], suite_collection=TestSuiteCollection([SUITE.ARCHIVE, SUITE.MAIN])
        )
        command = generator.generate()
        self.assertIn("--suite=archive,main", command)

    def test_set_test_suites_with_other_flags(self):
        """
        Test that setting test suites works alongside other flags.
        """
        generator = MTRGenerator(
            flags=[MTROption(MTR.FORCE, True)],
            suite_collection=TestSuiteCollection([SUITE.ARCHIVE, SUITE.MAIN]),
        )
        command = generator.generate()
        self.assertIn("--force", command)
        self.assertIn("--suite=archive,main", command)
