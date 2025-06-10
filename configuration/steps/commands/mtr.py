from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command
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
    """

    def __init__(
        self,
        name: str,
        testcase: MTRGenerator,
        workdir: PurePath = PurePath("mysql-test"),
        mtr_feedback_plugin: bool = False,
        save_logs_path: PurePath = PurePath("."),
    ):
        self.name = f"MTR - {name}"
        super().__init__(name=self.name, workdir=workdir)
        assert isinstance(testcase, MTRGenerator)
        self.testcase = testcase
        self.mtr_feedback_plugin = int(mtr_feedback_plugin)
        self.save_logs_path = save_logs_path
        self.log_path = self.workdir / "/var"  # default of MTR, if vardir is not set
        self.archive_name = f"{name}.tar.gz"

        for opt in self.testcase.flags:
            if opt.name == "vardir":
                self.log_path = opt.value
                break

    def as_cmd_arg(self) -> list[str]:
        mtr_cmd = " ".join(self.testcase.generate())
        return [
            "bash",
            "-exc",
            f"""
            MTR_FEEDBACK_PLUGIN={self.mtr_feedback_plugin} {mtr_cmd} || ({self._save_logs()})
            """,
        ]

    def _save_logs(self) -> str:
        logs = ["*.log", "*.err", "core*"]
        patterns = " -o ".join([f'-iname "{log}"' for log in logs])
        return f"""
            echo "Saving MTR logs"
            cd {self.log_path}
            mkdir -p {self.save_logs_path}
            find . -type f \( {patterns} \) -print0 | rsync -a --files-from=- --from0 ./ {self.save_logs_path}/
            exit 1
            """
