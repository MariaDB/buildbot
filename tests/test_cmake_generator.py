import unittest

from steps.cmake.compilers import CompilerCommand
from steps.cmake.generator import CMakeGenerator, DuplicateFlagException
from steps.cmake.options import CMAKE, PLUGIN, WITH, BuildConfig, BuildType, CMakeOption


class TestCMakeGenerator(unittest.TestCase):
    def test_initialization_with_flags(self):
        """Test that the generator initializes with provided flags."""
        flags = [
            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
            CMakeOption(CMAKE.INSTALL_PREFIX, "/usr/local"),
            CMakeOption(PLUGIN.ARCHIVE_STORAGE_ENGINE, True),
            CMakeOption(WITH.ASAN, True),
        ]
        generator = CMakeGenerator(flags=flags)
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
                "-DCMAKE_INSTALL_PREFIX=/usr/local",
                "-DPLUGIN_ARCHIVE=ON",
                "-DWITH_ASAN=ON",
            ],
        )

    def test_append_flags_successful(self):
        """
        Test that flags are appended successfully.
        """
        generator = CMakeGenerator(flags=[])
        generator.append_flags(
            [
                CMakeOption(CMAKE.LIBRARY_PATH, "/usr/lib"),
                CMakeOption(CMAKE.AR, "ar"),
            ]
        )
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DCMAKE_AR=ar",
                "-DCMAKE_LIBRARY_PATH=/usr/lib",
            ],
        )

    def test_append_flags_duplicate(self):
        """
        Test that appending a duplicate flag raises an exception.
        """
        flags = [CMakeOption(CMAKE.BUILD_TYPE, "Release")]
        generator = CMakeGenerator(flags=flags)
        duplicate_flag = CMakeOption(CMAKE.BUILD_TYPE, "Debug")
        with self.assertRaises(DuplicateFlagException):
            generator.append_flags([duplicate_flag])

    def test_set_compiler(self):
        """
        Test that set_compiler adds the correct flags.
        """
        generator = CMakeGenerator(flags=[])
        compiler = CompilerCommand(cc="gcc", cxx="g++")
        generator.set_compiler(compiler)
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DCMAKE_CXX_COMPILER=g++",
                "-DCMAKE_C_COMPILER=gcc",
            ],
        )

    def test_use_ccache(self):
        """
        Test that use_ccache sets the correct flags.
        """
        generator = CMakeGenerator(flags=[])
        generator.use_ccache()
        command = generator.generate()
        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
                "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
            ],
        )

    def test_generate_with_no_flags(self):
        """
        Test that generate produces only the 'cmake' command if no flags are
        set.
        """
        generator = CMakeGenerator(flags=[])
        command = generator.generate()
        self.assertEqual(command, ["cmake", "."])

    def test_set_build_config(self):
        """
        Test that set_build_config correctly adds the BUILD_CONFIG flag.
        """
        generator = CMakeGenerator(flags=[])

        # Set the build config to MYSQL_RELEASE
        generator.set_build_config(BuildConfig.MYSQL_RELEASE)
        command = generator.generate()

        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DBUILD_CONFIG=mysql_release",
            ],
        )

    def test_set_build_config_duplicate(self):
        """
        Test that setting BUILD_CONFIG twice raises a DuplicateFlagException.
        """
        generator = CMakeGenerator(flags=[])

        # Set the build config the first time
        generator.set_build_config(BuildConfig.MYSQL_RELEASE)

        # Attempt to set it again should raise DuplicateFlagException
        with self.assertRaises(DuplicateFlagException):
            generator.set_build_config(BuildConfig.MYSQL_RELEASE)

    def test_set_build_config_with_other_flags(self):
        """
        Test that set_build_config works alongside other flags.
        """
        generator = CMakeGenerator(
            flags=[CMakeOption(CMAKE.INSTALL_PREFIX, "/usr/lib/test")]
        )

        # Set the build config
        generator.set_build_config(BuildConfig.MYSQL_RELEASE)
        command = generator.generate()

        self.assertEqual(
            command,
            [
                "cmake",
                ".",
                "-DBUILD_CONFIG=mysql_release",
                "-DCMAKE_INSTALL_PREFIX=/usr/lib/test",
            ],
        )
