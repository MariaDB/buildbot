from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


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


class UBIEnableFIPS(Command):
    """
    A command to enable FIPS mode in Red Hat-based systems.
    Attributes:
        name (str): The name of the command.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self):
        name = "Enable FIPS in UBI container"
        super().__init__(name=name, workdir=PurePath("."), user="root")

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            """
                # Check if OpenSSL is installed
                if ! command -v openssl &> /dev/null; then
                    echo "OpenSSL is not installed."
                    exit 1
                fi

                # Enable FIPS mode in RedHat OpenSSL
                sed -i -e '/\[ evp_properties \]/a default_properties = fips=yes' \
                    -e '/opensslcnf.config/a .include = /etc/crypto-policies/back-ends/openssl_fips.config' \
                    -e '/\[provider_sect\]/a fips = fips_sect' \
                    /etc/pki/tls/openssl.cnf


                # List providers. If FIPS is not listed, it may not be enabled.
                if ! openssl list -providers | grep -q 'fips'; then
                    echo "FIPS provider is not enabled."
                    exit 1
                fi

                # If FIPS is enabled then generating a hash with MD5 should fail
                if openssl dgst -md5 /dev/null &> /dev/null; then
                    echo "FIPS mode is not enabled."
                    exit 1
                else
                    echo "FIPS mode is enabled."
                    exit 0
                fi
            """,
        ]


class AnyCommand(Command):
    """
    A command that executes any arbitrary shell command.
    This command is useful for running custom shell commands that do not fit into predefined categories.
    Attributes:
        name (str): The name of the command.
        workdir (PurePath): The working directory for the command.
        command (str): The shell command to execute. Support for interpolation is provided.
    """

    def __init__(self, name: str, command: str, workdir: PurePath = PurePath(".")):
        super().__init__(name=name, workdir=workdir)
        self.command = command

    def as_cmd_arg(self) -> list[str]:
        return ["bash", "-exc", util.Interpolate(self.command)]
