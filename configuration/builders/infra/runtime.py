import copy
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterable

from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from configuration.steps.base import BaseStep
from configuration.steps.remote import ShellStep


class BuildSequence:
    """
    A class to manage a sequence of build steps.
    This class allows you to add steps to a sequence and retrieve them as an iterable.
    Attributes:
        steps (list[BaseStep]): A list of build steps in the sequence.
    Methods:
        get_steps() -> Iterable[BaseStep]:
            Returns an iterable of the build steps in the sequence.
        add_step(step: BaseStep):
            Adds a build step to the sequence.
    """

    def __init__(self):
        self.steps = []

    def get_steps(self) -> Iterable[BaseStep]:
        return self.steps

    def add_step(self, step: BaseStep):
        self.steps.append(step)


@dataclass
class DockerConfig:
    """Configuration for a Docker container used in build steps.
    This class encapsulates the necessary parameters for running a build step inside a Docker container,
    including the Docker image, environment variables, volume mounts, and runtime settings.
    Attributes:
        repository (str): The Docker repository URL (e.g., quay.io/ghcr.io + org/repo).
        image_tag (str): The tag of the Docker image to use.
        bind_mounts (list[tuple[Path, Path]]): List of tuples specifying source and destination paths for bind mounts.
        env_vars (list[tuple[str, str]]): List of environment variables to set in the container.
        shm_size (str): Size of the shared memory for the container.
        memlock_limit (int): Memory lock limit for the container.
        workdir (PurePath): The working directory inside the container.
    """

    repository: str  # e.g. quay/ghcr + org/repo
    image_tag: str
    bind_mounts: list[tuple[Path, Path]]  # src, dst
    env_vars: list[tuple[str, str]]
    shm_size: str
    memlock_limit: int
    workdir: PurePath
    _container_name: str = None

    @property
    def image_url(self) -> str:
        return f"{self.repository}{self.image_tag}"

    @property
    def volume_mount(self):
        return f"type=volume,src={self._container_name},dst={self.workdir}"

    @property
    def runtime_tag(self) -> str:
        return f"buildbot:{self._container_name}"

    @property
    def container_name(self) -> str:
        if not self._container_name:
            raise ValueError("Container name is not set.")
        return self._container_name

    def __hash__(self):
        return hash((self.image_tag))


class InContainer(BaseStep):
    """
    A wrapper class for executing a ShellStep inside a Docker container.

    This class allows you to run a ShellStep or its subclasses within a Docker container,
    providing additional configuration options such as environment variables, volume mounts,
    and container runtime settings.

    Attributes:
        step (ShellStep): The ShellStep instance to be executed inside the container.
        docker_environment (DockerConfig): Configuration for the Docker container, including
            environment variables, volume mounts, and runtime settings.
        container_commit (bool): Whether to commit the container after execution. Defaults to False.
        workdir (PurePath): The working directory for the step command.

    Methods:
        generate() -> IBuildStep:
            Generates the build step with the Docker container configuration applied.
            This includes setting up the Docker command prefix, environment variables,
            volume mounts, and working directory.
    """

    def __init__(
        self,
        step: ShellStep,
        docker_environment: DockerConfig,
        container_commit: bool = False,
    ) -> ShellStep:
        super().__init__(name=step.name)
        assert isinstance(
            step, ShellStep
        ), "InContainer wrapper only works with ShellStep or its subclasses"
        self.step = step
        self.container_commit = container_commit
        self.docker_environment = docker_environment
        self.workdir = step.command.workdir

    def generate(self) -> IBuildStep:
        step = copy.deepcopy(self.step)
        cmd_prefix = []
        cmd_prefix.append(
            [
                "docker",
                "run",
                "--init",
                "--name",
                f"{self.docker_environment.container_name}",
                "-u",
                f"{step.command.user}",
            ]
        )
        # Mandatory volume mount for state sharing between steps
        cmd_prefix.append(
            [
                "--mount",
                self.docker_environment.volume_mount,
            ]
        )

        if not self.container_commit:
            cmd_prefix.append(["--rm"])

        # User defined bind mounts
        for src, dst in self.docker_environment.bind_mounts:
            cmd_prefix.append(
                [
                    "--mount",
                    f"type=bind,src={src},dst={dst}",
                ]
            )

        # Global variables form the base
        env_vars = dict(self.docker_environment.env_vars)
        # Step variables override global variables
        env_vars.update(step.env_vars)
        for variable, value in env_vars.items():
            cmd_prefix.append(["-e", util.Interpolate(f"{variable}={value}")])

        cmd_prefix.append([f"--shm-size={self.docker_environment.shm_size}"])

        path = self.docker_environment.workdir / step.command.workdir
        # Absolute command workdir overrides basedir.
        if step.command.workdir.is_absolute():
            path = step.command.workdir

        cmd_prefix.append(["-w", path.as_posix()])

        cmd_prefix.append([self.docker_environment.runtime_tag])

        step.prefix_cmd.extend(cmd_prefix)

        step.command.workdir = PurePath(".")
        return step.generate()
