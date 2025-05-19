from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class CreateS3Bucket(Command):
    def __init__(self, bucket: str, workdir: PurePath = PurePath(".")):
        name = "Create S3 bucket"
        self.bucket = bucket
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            f"mc mb minio/{self.bucket}",
        ]


class DeleteS3Bucket(Command):
    def __init__(self, bucket: str, workdir: PurePath = PurePath(".")):
        name = "Delete S3 bucket"
        self.bucket = bucket
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            f"mc rb --force minio/{self.bucket}",
        ]


class SaveCompressedTar(Command):
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
            "-ec",
            util.Interpolate(
                f"""
            mkdir -p {self.destination}
            tar --exclude='.[^/]*' -czvf {self.destination}/{self.archive_name}.tar.gz .;
            """
            ),
        ]
        return result


class FindFiles(Command):
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
            "-ec",
            f'find . -maxdepth 1 -type f -name "{self.include}" ! -name "{self.exclude}" | xargs',
        ]


class PrintEnvironmentDetails(Command):
    def __init__(self):
        name = "Print environment details"
        super().__init__(name=name, workdir=PurePath("."))

    def as_cmd_arg(self) -> list[str]:
        return (
            [
                "bash",
                "-c",
                """
                date -u
                uname -a
                ulimit -a
                command -v lscpu >/dev/null && lscpu
                LD_SHOW_AUXV=1 sleep 0
            """,
            ],
        )
