from abc import ABC, abstractmethod
from typing import Callable, Iterable

from buildbot.interfaces import IBuildStep
from buildbot.plugins import util
from buildbot.process.builder import Builder
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.factory import BuildFactory
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from configuration.builders.infra.runtime import (
    BuildSequence,
    CleanupDockerResources,
    CleanupWorkerDir,
    ContainerCommit,
    CreateDockerWorkdirs,
    FetchContainerImage,
    TagContainerImage,
)
from configuration.workers.base import WorkerBase


class BaseBuilder:
    def __init__(self, name: str):
        self.name = name
        self.build_sequences: list[BuildSequence] = []
        self.prepare_steps = []
        self.active_steps = []
        self.cleanup_steps = []

    def add_sequence(self, sequence: BuildSequence):
        self.build_sequences.append(sequence)

    def get_factory(self) -> BuildFactory:
        factory = BuildFactory()

        has_docker_enivornment = False
        docker_config = None
        docker_workdirs = []

        self.prepare_steps.append(CleanupWorkerDir(name="previous-run"))

        for seq in self.build_sequences:
            for step in seq.get_steps():
                if hasattr(step, "run_in_container") and step.run_in_container:
                    if (
                        str(step.command.workdir) not in docker_workdirs
                        and not step.command.workdir.is_absolute()
                    ):
                        docker_workdirs.append(str(step.command.workdir))

                    if not has_docker_enivornment:
                        has_docker_enivornment = True
                        self.prepare_steps.append(
                            CleanupDockerResources(
                                name="previous", config=step.docker_environment
                            )
                        )
                        self.cleanup_steps.append(
                            CleanupDockerResources(
                                name="current", config=step.docker_environment
                            )
                        )

                    if docker_config != step.docker_environment:
                        docker_config = step.docker_environment
                        self.prepare_steps.append(
                            FetchContainerImage(config=step.docker_environment)
                        )
                        # Active step below is on purpose. This will delete the old image and create a tag
                        # for the new image when the user decided to change it
                        self.active_steps.append(
                            TagContainerImage(config=step.docker_environment)
                        )
                        docker_config = step.docker_environment
                    self.active_steps.append(step.generate())

                    if step.container_commit:
                        self.active_steps.append(
                            ContainerCommit(
                                config=step.docker_environment, step_name=step.name
                            )
                        )
                else:
                    self.active_steps.append(step.generate())

        # Add docker workdirs
        # Doesn't matter which config is used, what is important is to create the workdirs
        # in the volume mount, relative to the base workdir (/home/buildbot),
        if docker_workdirs:
            self.prepare_steps.append(
                CreateDockerWorkdirs(config=docker_config, workdirs=docker_workdirs)
            )

        self.cleanup_steps.append(CleanupWorkerDir(name="current-run"))

        factory.addSteps(self.prepare_steps + self.active_steps + self.cleanup_steps)

        return factory

    def get_config(
        self,
        workers: Iterable[WorkerBase],
        can_start_build: Callable[
            [Builder, AbstractWorkerForBuilder, BuildRequest], bool
        ],
        next_build: Callable[[Builder, Iterable[BuildRequest]], BuildRequest],
        tags: list[str] = [],
        properties: dict[str, str] = {},
    ) -> util.BuilderConfig:
        return util.BuilderConfig(
            name=self.name,
            workernames=workers,
            tags=tags,
            nextBuild=next_build,
            canStartBuild=can_start_build,
            factory=self.get_factory(),
            properties=properties,
        )


class GenericBuilder(BaseBuilder):
    def __init__(self, name, sequences):
        super().__init__(name)
        for sequence in sequences:
            self.add_sequence(sequence)
