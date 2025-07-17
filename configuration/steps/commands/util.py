from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import BashScriptCommand, Command


class CreateS3Bucket(Command):
    """
    A command to create an S3 bucket using MinIO client (mc).
    This command initializes a new S3 bucket in the MinIO server.
    Attributes:
        bucket (str): The name of the S3 bucket to create.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self, bucket: str, workdir: PurePath = PurePath(".")):
        name = "Create S3 bucket"
        self.bucket = bucket
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(f"mc mb minio/{self.bucket}"),
        ]


class DeleteS3Bucket(Command):
    """
    A command to delete an S3 bucket using MinIO client (mc).
    This command removes an existing S3 bucket from the MinIO server.
    Attributes:
        bucket (str): The name of the S3 bucket to delete.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self, bucket: str, workdir: PurePath = PurePath(".")):
        name = "Delete S3 bucket"
        self.bucket = bucket
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(f"mc rb --force minio/{self.bucket}"),
        ]


class SaveCompressedTar(Command):
    """
    A command to create a compressed tar archive of the current working directory.
    This command archives the contents of the current directory, excluding hidden files,
    and saves it to a specified destination with a given archive name.
    Attributes:
        name (str): The name of the command.
        workdir (PurePath): The working directory for the command.
        archive_name (str): The name of the archive file to create.
        destination (str): The destination directory where the archive will be saved.
    """

    def __init__(
        self,
        name: str,
        workdir: PurePath,
        archive_name: str,
        destination: str,
    ):
        self.name = name
        self.archive_name = archive_name
        self.destination = destination
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
            mkdir -p {self.destination}
            tar --exclude='.[^/]*' -czvf {self.destination}/{self.archive_name}.tar.gz .;
            """
            ),
        ]
        return result


class FindFiles(Command):
    """
    A command to find files in the current directory based on a specified pattern.
    This command lists files that match the given include pattern and optionally excludes
    files that match the exclude pattern.
    Attributes:
        include (str): The pattern to include files.
        exclude (str): The pattern to exclude files (default: empty string).
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self, include: str, exclude: str = "", workdir: PurePath = PurePath(".")
    ):
        self.include = include
        self.exclude = exclude
        name = f"List {include}"
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f'find . -maxdepth 1 -type f -name "{self.include}" ! -name "{self.exclude}" | xargs',
        ]


class PrintEnvironmentDetails(Command):
    """
    A command to print environment details for debugging purposes.
    This command outputs various system information such as date, system architecture,
    resource limits, CPU information.
    Attributes:
        name (str): The name of the command.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self):
        name = "Print environment details"
        super().__init__(name=name, workdir=PurePath("."))

    def as_cmd_arg(self) -> list[str]:
        return (
            [
                "bash",
                "-exc",
                """
                date -u
                uname -a
                ulimit -a
                command -v lscpu >/dev/null && lscpu
                LD_SHOW_AUXV=1 sleep 0
            """,
            ],
        )


class UBIEnableFIPS(BashScriptCommand):
    """
    A command to enable FIPS mode on UBI containers.
    """

    def __init__(self):
        super().__init__(script_name="ubi_enable_fips.sh", user="root")


class GetSSLTests(BashScriptCommand):
    """
    A command to extract the list of SSL tests to run from the MariaDB test suite.
    """

    def __init__(self, output_file: str):
        args = [output_file]
        super().__init__(script_name="get_fips_mtr_tests.sh", args=args)


class LDDCheck(BashScriptCommand):
    """
    A command to check dynamic library dependencies of specified binaries.
    """

    def __init__(
        self,
        binary_checks: dict[str, list[str]],
    ):
        args = [f"{binary}:{','.join(libs)}" for binary, libs in binary_checks.items()]
        super().__init__(script_name="ldd_check.sh", args=args)
