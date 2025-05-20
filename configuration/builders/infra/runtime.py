import copy
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterable

from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from configuration.steps.base import BaseStep
from configuration.steps.remote import ShellStep


class BuildSequence:
    def __init__(self):
        self.steps = []

    def get_steps(self) -> Iterable[BaseStep]:
        return self.steps

    def add_step(self, step: BaseStep):
        self.steps.append(step)

@dataclass
class DockerConfig:
    repository: str  # e.g. quay/ghcr + org/repo
    image_tag: str
    container_name: str
    bind_mounts: list[tuple[Path, Path]]  # src, dst
    env_vars: list[tuple[str, str]]
    shm_size: str
    memlock_limit: int
    workdir: PurePath

    @property
    def image_url(self) -> str:
        return f"{self.repository}{self.image_tag}"

    @property
    def volume_mount(self):
        return f"type=volume,src={self.container_name},dst={self.workdir}"

    @property
    def runtime_tag(self) -> str:
        return f"buildbot:{self.container_name}"


class InContainer(BaseStep):
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
        cmd_prefix = []
        self.step = copy.deepcopy(step)
        self.container_commit = container_commit
        self.docker_environment = docker_environment
        self.workdir = self.step.command.workdir

        cmd_prefix.append(
            [
                "docker",
                "run",
                "--init",
                "--name",
                f"{docker_environment.container_name}",
                "-u",
                f"{self.step.command.user}",
            ]
        )
        # Mandatory volume mount for state sharing between steps
        cmd_prefix.append(
            [
                "--mount",
                docker_environment.volume_mount,
            ]
        )

        if not container_commit:
            cmd_prefix.append(["--rm"])

        # User defined bind mounts
        for src, dst in docker_environment.bind_mounts:
            cmd_prefix.append(
                [
                    "--mount",
                    f"type=bind,src={src},dst={dst}",
                ]
            )

        # Global variables form the base
        env_vars = dict(docker_environment.env_vars)
        # Step variables override global variables
        env_vars.update(self.step.env_vars)
        for variable, value in env_vars.items():
            cmd_prefix.append(["-e", util.Interpolate(f"{variable}={value}")])

        cmd_prefix.append([f"--shm-size={docker_environment.shm_size}"])

        path = docker_environment.workdir / step.command.workdir
        # Absolute command workdir overrides basedir.
        if self.step.command.workdir.is_absolute():
            path = self.step.command.workdir

        cmd_prefix.append(["-w", path.as_posix()])

        cmd_prefix.append([docker_environment.runtime_tag])

        self.step.prefix_cmd.extend(cmd_prefix)

        self.step.command.workdir = PurePath(".")
    
    def generate(self) -> IBuildStep:
        return self.step.generate()

