import os
from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import BashScriptCommand, Command
from configuration.steps.generators.mtr.generator import MTRGenerator


class MTRTest(Command):
    """
    A command to run MySQL Test Runner (MTR) tests.
    This command executes MTR tests based on the provided test case generator.
    Attributes:
        name (str): The name of the command.
        testcase (MTRGenerator): The test case generator for MTR tests.
        workdir (PurePath): The working directory for the command.
        mtr_feedback_plugin (bool): Whether to enable MTR feedback plugin.
        save_logs_path (PurePath): The path where logs will be saved.
        log_path (PurePath): The path where MTR logs are stored.
        archive_name (str): The name of the archive file to create.
        tests_from_file (str): Optional path to a file containing tests to run.
    """

    def __init__(
        self,
        name: str,
        testcase: MTRGenerator,
        workdir: PurePath = PurePath("mysql-test"),
        mtr_feedback_plugin: bool = False,
        save_logs_path: PurePath = PurePath("."),
        tests_from_file: PurePath = None,
    ):
        self.name = f"MTR - {name}"
        super().__init__(name=self.name, workdir=workdir)
        assert isinstance(testcase, MTRGenerator)
        self.testcase = testcase
        self.mtr_feedback_plugin = int(mtr_feedback_plugin)
        self.save_logs_path = save_logs_path
        self.log_path = self.workdir / "/var"  # default of MTR, if vardir is not set
        self.archive_name = f"{name}.tar.gz"
        self.tests_from_file = tests_from_file

        for opt in self.testcase.flags:
            if opt.name == "vardir":
                self.log_path = opt.value
                break

    def as_cmd_arg(self) -> list[str]:
        mtr_cmd = " ".join(self.testcase.generate())
        if self.tests_from_file:
            incompatible_flags = ["do-test", "suites", "suite"]
            has_incompatible_flag = any(
                option in str(self.testcase.flags) for option in incompatible_flags
            )

            assert not has_incompatible_flag, (
                "If tests_from_file was provided then do not use "
                "--suite(s) or --do-test flags"
            )
            mtr_cmd += " $(< {})".format(str(self.tests_from_file))
        return [
            "bash",
            "-exc",
            f"""
            MTR_FEEDBACK_PLUGIN={self.mtr_feedback_plugin} {mtr_cmd} || ({self._save_logs()})
            """,
        ]

    def _save_logs(self) -> str:
        logs = ["*.log", "*.err*", "core*"]
        patterns = " -o ".join([f'-iname "{log}"' for log in logs])
        return f"""
            #!/bin/bash

            script_dir=$(pwd) # Path where the test runner was invoked
            vardir="{self.log_path}"
            save_logs_path="{self.save_logs_path}"
            save_bin_path=$(dirname "$save_logs_path")
            file_patterns_to_save="{patterns}"

            # MTR can run both from installed binaries or from build tree
            # Try to find mariadbd binary and plugins in both cases
            if [ -d /usr/lib/mysql/plugin ]; then
                plugins_dir="/usr/lib/mysql/plugin"
            elif [ -d /usr/lib64/mysql/plugin ]; then
                plugins_dir="/usr/lib64/mysql/plugin"
            else
                plugins_dir="$vardir/plugins"
            fi
            mariadbd_path=$(command -v mariadbd 2>/dev/null || ([ -x $script_dir/../sql/mariadbd ] && realpath $script_dir/../sql/mariadbd))

            echo "Saving MTR logs"

            # Staging path before files are moved to CI
            mkdir -p $save_logs_path

            # Save plugins .so and mariadbd if core was generated
            save_bin=0
            find $vardir -name *core.* -exec false {{}} + || save_bin=1
            if [[ $save_bin -ne 0 ]]; then
                find -L "$plugins_dir" -maxdepth 1 -type f -name '*.so' -printf '%f\n' > $save_bin_path/plugins_list.txt
                tar -czvf "$save_bin_path/plugins.tar.gz" --dereference -C "$plugins_dir" -T $save_bin_path/plugins_list.txt
                gzip -c "$mariadbd_path" > "$save_bin_path/mariadbd.gz"
            fi

            # Some core files are left uncompressed by MTR
            find $vardir -iregex ".*/core\(\.[0-9]+\)?" -ls -exec gzip {{}} +

            # Copy pattern matching files to staging
            cd "$vardir" && find . -type f \( $file_patterns_to_save \) -print0 | rsync -a --from0 --files-from=- ./ "$save_logs_path/"
            exit 1 # Script was invoked by an MTR failure so we must mark the step as failed
            """


class MTRReporter(BashScriptCommand):
    """
    A command to transfer all the MTR JUnit test results to the mtr_junit_collector service.
    Attributes:
        directory (PurePath): The directory containing the MTR test results.
    """

    JUNIT_COLLECTOR_BASE_URL = os.environ.get("JUNIT_COLLECTOR_BASE_URL")

    def __init__(self, workdir: PurePath = PurePath(".")):
        base_url = self.JUNIT_COLLECTOR_BASE_URL
        branch = util.Interpolate("%(prop:branch)s")
        revision = util.Interpolate("%(prop:revision)s")
        platform = util.Interpolate("%(prop:buildername)s")
        bbnum = util.Interpolate("%(prop:buildnumber)s")
        dir = "."

        args = [base_url, branch, revision, platform, bbnum, dir]
        super().__init__(script_name="mtr_reporter.sh", args=args, workdir=workdir)
        self.name = "Save test results for CrossReference"
