from pathlib import PurePath

from configuration.steps.commands.base import Command


class CreateDockerWorkdirs(Command):
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
            "-ec",
            f"mkdir -p . {' '.join(self.workdirs)} ",
        ]


class CleanupDockerResources(Command):
    def __init__(self, name: str, container_name: str, runtime_tag: str):
        super().__init__(
            name=f"Cleanup Docker resources - {name}", workdir=PurePath(".")
        )
        self.container_name = container_name
        self.runtime_tag = runtime_tag

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            f"""
            (
                docker rm --force {self.container_name};
                docker volume rm {self.container_name};
                docker image rm {self.runtime_tag};
            ) || true
            """,
        ]


class FetchContainerImage(Command):
    def __init__(self, image_url: str):
        super().__init__(name=f"Fetch container image", workdir=PurePath("."))
        self.image_url = image_url

    def as_cmd_arg(self) -> list[str]:
        return ["docker", "pull", self.image_url]


class TagContainerImage(Command):
    def __init__(self, image_url: str, runtime_tag: str):
        super().__init__(
            name=f"Prepare runtime container image tag", workdir=PurePath(".")
        )
        self.image_url = image_url
        self.runtime_tag = runtime_tag

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-ec",
            (
                f"docker image rm -f {self.runtime_tag} && "
                f"docker tag {self.image_url} {self.runtime_tag}"
            ),
        ]


class ContainerCommit(Command):
    def __init__(self, container_name: str, runtime_tag: str, step_name: str):
        super().__init__(
            name=f"Checkpoint {step_name}", workdir=PurePath(".")
        )
        self.container_name = container_name
        self.runtime_tag = runtime_tag
        self.step_name = step_name

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-c",
            (
                "docker container commit "
                f"""--message "{self.step_name}" {self.container_name} """
                f"{self.runtime_tag} && "
                f"docker rm {self.container_name}"
            ),
        ]


class CleanupWorkerDir(Command):
    def __init__(self, name: str):
        super().__init__(
            name=f"Cleanup Worker Directory - {name}", workdir=PurePath(".")
        )

    def as_cmd_arg(self) -> list[str]:
        return ["bash", "-ec", "rm -r * .* 2> /dev/null || true"]
