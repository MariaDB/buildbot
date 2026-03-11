import copy
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Iterable, Optional

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
class ContainerBase:
    """Base container configuration"""

    repository: str
    image_tag: str
    env_vars: list[tuple[str, str]] = field(default_factory=list)
    platform: Optional[str] = field(default=None)

    _container_name: Optional[str] = field(init=False, default=None)
    _network: Optional[str] = field(init=False, default=None)

    @property
    def image_url(self) -> str:
        return f"{self.repository}{self.image_tag}"

    @property
    def container_name(self) -> str:
        if not self._container_name:
            raise ValueError("Container name is not set.")
        return self._container_name

    @property
    def network(self) -> Optional[str]:
        return self._network

    def __hash__(self):
        return hash((self.image_tag))


@dataclass
class DockerConfig(ContainerBase):
    """Docker configuration for running a containerized build step"""

    __hash__ = ContainerBase.__hash__
    shm_size: Optional[str] = field(default="15g")
    memlock_limit: Optional[int] = field(default=67108864)
    bind_mounts: list[tuple[Path, Path]] = field(default_factory=list)
    workdir: Optional[PurePath] = field(default=PurePath("/home/buildbot"))

    @property
    def volume_mount(self) -> str:
        return f"type=volume,src={self.container_name},dst={self.workdir}"

    @property
    def runtime_tag(self) -> str:
        return f"buildbot:{self.container_name}"


@dataclass
class Sidecar(ContainerBase):
    """Sidecar container configuration"""

    __hash__ = ContainerBase.__hash__
    tmpfs: PurePath = field(default=PurePath("/tmp"))


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

        self.step = copy.deepcopy(step)
        super().__init__(
            name=self.step.name, options=self.step.options
        ), "InContainer wrapper only works with ShellStep or its subclasses"
        self.container_commit = container_commit
        self.docker_environment = docker_environment
        self.workdir = step.command.workdir

    def generate(self) -> IBuildStep:
        step = self.step
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

        if self.docker_environment.network:
            cmd_prefix.append(["--network", self.docker_environment.network])

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

        step.env_vars = []  # Reset env_vars in the step as they are now set by docker

        cmd_prefix.append([f"--shm-size={self.docker_environment.shm_size}"])
        cmd_prefix.append(
            ["--ulimit", f"memlock={self.docker_environment.memlock_limit}"]
        )

        path = self.docker_environment.workdir / step.command.workdir
        # Absolute command workdir overrides basedir.
        if step.command.workdir.is_absolute():
            path = step.command.workdir

        cmd_prefix.append(["-w", path.as_posix()])
        cmd_prefix.append([self.docker_environment.runtime_tag])

        step.prefix_cmd.extend(cmd_prefix)

        step.command.workdir = PurePath(".")
        return step.generate()
