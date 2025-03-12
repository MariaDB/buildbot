from typing import Iterable
from dataclasses import dataclass
from pathlib import Path

from buildbot.interfaces import IBuildStep
from buildbot.plugins import steps, util
from steps.base import Command
from builders.base import BuildSequence


@dataclass
class DockerConfig:
    image_tag: str               # Image tag used to pull the container
    volume_mounts: list[tuple[Path, Path, str]]
    env_vars: list[tuple[str, str]]
    shm_size: str
    memlock_limit: int


class FetchContainerImage(steps.ShellCommand):
    def __init__(self, config: DockerConfig):
        self.config = config
        super().__init__(name=f"Fetch Container Image - {config.image_tag}",
                         command=['docker', 'pull', config.image_tag])


class RunInContainer:
    def __init__(self,
                 container_config: DockerConfig,
                 commands: list[Command]):
        self.config = container_config
        self.commands = commands
        print(commands)

    def generate(self) -> list[IBuildStep]:
        result = []
        folders = []
        for src, _, _ in self.config.volume_mounts:
            folders.append(src)
        if folders:
            subst_str = '%s ' * len(folders)
            folders = folders * 2
            result += [
                steps.ShellCommand(name='Prepare environment',
                                   command=util.Interpolate(
                                       f'mkdir -p {subst_str} && '
                                       f'chown -R 1000:1000 {subst_str};',
                                       *folders))
            ]

        for command in self.commands:
            r_command = [
                'docker',
                'run',
                '--rm',
            ]
            for src, dst, flags in self.config.volume_mounts:
                r_command += [
                    '--mount',
                    util.Interpolate('type=bind,src=%s,dst=%s,bind-propagation=rshared', src, dst)
                ]
            # TODO value quoting
            r_command += [
                f'-e {name}={value}'
                for name, value in self.config.env_vars
            ]
            r_command += [f'--shm-size={self.config.shm_size}']
            # TODO(cvicentiu) This workdir is hacky.
            r_command += ['-w', f'/home/buildbot/{command.workdir}']
            r_command += [
                self.config.image_tag
            ]
            r_command += command.as_cmd_arg()

            print(r_command)
            print(command.name)

            result.append(steps.ShellCommand(name=command.name,
                                             command=r_command))
        return result


class InContainerBuildSequence(BuildSequence):
    def __init__(self, steps: list[Command], config: DockerConfig):
        self.config = config
        self.steps = steps

    def get_prepare_steps(self) -> Iterable[IBuildStep]:
        return [FetchContainerImage(self.config)]

    def get_active_steps(self) -> Iterable[IBuildStep]:
        return RunInContainer(container_config=self.config,
                              commands=steps).generate()

    def get_cleanup_steps(self) -> Iterable[IBuildStep]:
        return []
