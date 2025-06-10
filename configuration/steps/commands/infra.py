from pathlib import PurePath

from configuration.steps.commands.base import Command


class CreateDockerWorkdirs(Command):
    """
    A command to create work directories in a Docker container.
    This command runs a Docker container to create specified directories
    in the mounted volume, ensuring that the necessary workspaces are
    available for subsequent steps in the build process.
    Attributes:
        volume_mount (str): The Docker volume mount specification.
        image_url (str): The URL of the Docker image to use.
        workdirs (list[str]): A list of work directories to create in the container.
    """

    def __init__(self, volume_mount: str, image_url: str, workdirs: list[str]):
        name = "Create Docker Workdirs"
        super().__init__(name=name, workdir=PurePath("."))
        self.volume_mount = volume_mount
        self.image_url = image_url
        self.workdirs = workdirs

    def as_cmd_arg(self) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--mount",
            f"{self.volume_mount}",
            f"{self.image_url}",
            "bash",
            "-exc",
            f"mkdir -p . {' '.join(self.workdirs)} ",
        ]


class CleanupDockerResources(Command):
    """
    A command to clean up Docker resources after a build step.
    This command removes the specified Docker container, its associated volume,
    and the runtime Docker image used for the build, ensuring that no leftover resources
    remain after the build process is complete.
    Attributes:
        name (str): The name of the cleanup command.
        container_name (str): The name of the Docker container to clean up.
        runtime_tag (str): The runtime tag for the Docker image to remove.
    """

    def __init__(self, name: str, container_name: str, runtime_tag: str):
        super().__init__(
            name=f"Cleanup Docker resources - {name}", workdir=PurePath(".")
        )
        self.container_name = container_name
        self.runtime_tag = runtime_tag

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
            (
                docker rm --force {self.container_name};
                docker volume rm {self.container_name};
                docker image rm {self.runtime_tag};
            ) || true
            """,
        ]


class FetchContainerImage(Command):
    """
    A command to fetch a Docker container image.
    This command pulls the specified Docker image from a registry,
    ensuring that the required image is available for the build process.
    Attributes:
        image_url (str): The URL of the Docker image to fetch.
    """

    def __init__(self, image_url: str):
        super().__init__(name=f"Fetch container image", workdir=PurePath("."))
        self.image_url = image_url

    def as_cmd_arg(self) -> list[str]:
        return ["docker", "pull", self.image_url]


class TagContainerImage(Command):
    """
    A command to tag a Docker container image.
    This command removes any existing tag for the specified runtime tag
    and then tags the fetched image with the runtime tag, preparing it
    for use in the build process.
    Attributes:
        image_url (str): The URL of the Docker image to tag.
        runtime_tag (str): The runtime tag to apply to the Docker image.
    """

    def __init__(self, image_url: str, runtime_tag: str):
        super().__init__(
            name=f"Prepare runtime container image tag", workdir=PurePath(".")
        )
        self.image_url = image_url
        self.runtime_tag = runtime_tag

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            (
                f"docker image rm -f {self.runtime_tag} && "
                f"docker tag {self.image_url} {self.runtime_tag}"
            ),
        ]


class ContainerCommit(Command):
    """
    A command to commit a Docker container to an image.
    This command commits the specified Docker container to a new image
    with a given runtime tag, allowing the current state of the container
    to be saved for future use. After committing, it removes the container.
    Attributes:
        container_name (str): The name of the Docker container to commit.
        runtime_tag (str): The runtime tag for the new Docker image.
        step_name (str): The name of the step for identification.
    """

    def __init__(self, container_name: str, runtime_tag: str, step_name: str):
        super().__init__(name=f"Checkpoint {step_name}", workdir=PurePath("."))
        self.container_name = container_name
        self.runtime_tag = runtime_tag
        self.step_name = step_name

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            (
                "docker container commit "
                f"""--message "{self.step_name}" {self.container_name} """
                f"{self.runtime_tag} && "
                f"docker rm {self.container_name}"
            ),
        ]


class CleanupWorkerDir(Command):
    """
    A command to clean up the worker directory.
    This command removes all files and directories in the current working directory,
    including hidden files, ensuring that the worker directory is clean for the next build step.
    Attributes:
        name (str): The name of the cleanup command.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(self, name: str):
        super().__init__(
            name=f"Cleanup Worker Directory - {name}", workdir=PurePath(".")
        )

    def as_cmd_arg(self) -> list[str]:
        return ["bash", "-exc", "rm -r * .* 2> /dev/null || true"]
