import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from configuration.steps.base import PrefixableStep


@dataclass
class DockerConfig:
    repository: str  # e.g. quay/ghcr + org/repo
    image_tag: str
    volume_mounts: list[tuple[Path, Path, str]]
    env_vars: list[tuple[str, str]]
    shm_size: str
    memlock_limit: int
    basedir: str


class CleanupDockerResources(steps.ShellCommand):
    def __init__(self, name, config: DockerConfig, buildername: str):
        self.buildername = buildername
        self.config = config
        super().__init__(
            name=f"Cleanup Docker resources - {name} run",
            command=[
                "bash",
                "-ec",
                util.Interpolate(
                    f"docker rm --force {self.buildername} || true && docker volume rm {self.buildername} || true && docker image rm buildbot:{self.buildername} || true"
                ),
            ],
            alwaysRun=True,
        )


class CleanupWorkerDir(steps.ShellCommand):
    def __init__(self, name):
        super().__init__(
            name=f"Cleanup Worker Directory - {name} run",
            command="rm -r * .* 2> /dev/null || true",
            haltOnFailure=True,
            alwaysRun=True,
        )


class PrintEnvironmentDetails(steps.ShellCommand):
    def __init__(self):
        super().__init__(
            name="Print Environment Details",
            command=[
                "bash",
                "-c",
                util.Interpolate(
                    """
                            date -u
                            uname -a
                            ulimit -a
                            command -v lscpu >/dev/null && lscpu
                            LD_SHOW_AUXV=1 sleep 0
                            """
                ),
            ],
            haltOnFailure=True,
        )


class FetchContainerImage(steps.ShellCommand):
    def __init__(self, config: DockerConfig):
        self.config = config
        super().__init__(
            name=f"Fetch Container Image - {config.image_tag}",
            command=["docker", "pull", config.repository + config.image_tag],
            haltOnFailure=True,
        )


class TagContainerImage(steps.ShellCommand):
    def __init__(self, config: DockerConfig, buildername: str):
        self.config = config
        self.buildername = buildername
        self.image = config.repository + config.image_tag
        super().__init__(
            name=f"Tag Container Image - {config.image_tag}",
            command=[
                "bash",
                "-ec",
                util.Interpolate(
                    f"docker image rm buildbot:{self.buildername} || true && docker tag {self.image} buildbot:{self.buildername}"
                ),
            ],
            haltOnFailure=True,
        )


class BuildSequence:
    def __init__(
        self,
        prepare_steps: Iterable[IBuildStep],
        active_steps: Iterable[IBuildStep],
        cleanup_steps: Iterable[IBuildStep],
    ):
        self.prepare_steps = prepare_steps
        self.active_steps = active_steps
        self.cleanup_steps = cleanup_steps

    # Steps that will be called at the beginning of the BaseBuilder's build
    # process.
    def get_prepare_steps(self) -> Iterable[IBuildStep]:
        return [
            PrintEnvironmentDetails(),
            CleanupWorkerDir("previous"),
        ] + self.prepare_steps

    # Generate steps that will be called after *all* prepare steps for all
    # attached build sequences are called.
    def get_active_steps(self) -> Iterable[IBuildStep]:
        return self.active_steps

    # Steps that will be called at the end of the BaseBuilder's build process.
    def get_cleanup_steps(self) -> Iterable[IBuildStep]:
        return [CleanupWorkerDir("current")] + self.cleanup_steps


class RunInContainer:
    def __init__(
        self,
        container_config: DockerConfig,
        active_steps: list[PrefixableStep],
        buildername: str,
        build_sequence: BuildSequence,
    ):
        self.config = container_config
        self.steps = active_steps
        self.buildername = buildername
        self.container_image = f"buildbot:{self.buildername}"
        self.build_sequence = build_sequence

    def generate(self) -> list[IBuildStep]:
        result = []
        # Create workdirs. Only relative paths
        workdirs = []
        for step in self.steps:
            if (
                step.command.workdir
                and step.command.workdir not in workdirs
                and not os.path.isabs(step.command.workdir)
            ):
                workdirs.append(step.command.workdir)
        if workdirs:
            result.append(
                steps.ShellCommand(
                    name=f"Prepare in container ({self.config.image_tag}) workdirs",
                    command=util.Interpolate(
                        (
                            "docker run --rm "
                            f"--mount type=volume,src={self.buildername},dst=/home/buildbot "
                            f"-w {self.config.basedir} "
                            f'{self.container_image} mkdir -p {" ".join(workdirs)}'
                        )
                    ),
                    haltOnFailure=True,
                )
            )
        for step in self.steps:
            step.add_cmd_prefix(
                [
                    "docker",
                    "run",
                    "--init",  # To proper handle signals
                    "--name",
                    util.Interpolate(f"{self.buildername}"),
                    "-u",
                    f"{step.command.user}",
                ]
            )

            if not hasattr(step, "checkpoint") or not step.checkpoint:
                step.add_cmd_prefix(["--rm"])

            for src, dst, type in self.config.volume_mounts:
                step.add_cmd_prefix(
                    [
                        "--mount",
                        util.Interpolate(f"type={type},src={src},dst={dst}"),
                    ]
                )
            # Add env vars (global << sequence >> + local << step >>)
            if step.env_vars:
                env_vars = {env[0]: env[1] for env in self.config.env_vars}
                env_vars.update({env[0]: env[1] for env in step.env_vars})
                env_vars = list(env_vars.items())
            else:
                env_vars = self.config.env_vars

            for env in env_vars:
                step.add_cmd_prefix(["-e", util.Interpolate(f"{env[0]}={env[1]}")])

            step.add_cmd_prefix([f"--shm-size={self.config.shm_size}"])

            # Ignore basedir when an absolute path is given
            if os.path.isabs(step.command.workdir):
                step.add_cmd_prefix(["-w", f"{step.command.workdir}"])
            else:
                # (TODO: Razvan) No guarantee that this is a valid relative path
                step.add_cmd_prefix(
                    ["-w", f"{self.config.basedir}/{step.command.workdir}"]
                )

            step.add_cmd_prefix([self.container_image])

            # User defined step to run in the container
            result.append(step.generate())

            # Create a checkpoint
            if hasattr(step, "checkpoint") and step.checkpoint:
                result.append(
                    steps.ShellCommand(
                        name=f"Checkpoint {step.name}",
                        command=[
                            "bash",
                            "-c",
                            util.Interpolate(
                                f"docker commit {self.buildername} buildbot:{self.buildername} && docker rm {self.buildername}"
                            ),
                        ],
                        haltOnFailure=True,
                    )
                )

        self.build_sequence.prepare_steps.extend(
            [
                CleanupDockerResources(
                    name="previous", config=self.config, buildername=self.buildername
                ),
                FetchContainerImage(self.config),
                TagContainerImage(self.config, self.buildername),
            ]
        )
        self.build_sequence.active_steps.extend(result)

        self.build_sequence.cleanup_steps.append(
            CleanupDockerResources(
                name="current", config=self.config, buildername=self.buildername
            )
        )
