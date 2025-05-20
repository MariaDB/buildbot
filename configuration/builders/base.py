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
    InContainer,
    add_docker_create_workdirs_step,
    add_docker_cleanup_step,
    add_docker_fetch_step,
    add_docker_tag_step,
    add_docker_commit_step,
    add_worker_cleanup_step,
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

        self.prepare_steps.append(add_worker_cleanup_step(name="previous-run").generate())

        for seq in self.build_sequences:
            for step in seq.get_steps():
                if isinstance(step, InContainer):
                    if (
                        str(step.workdir) not in docker_workdirs
                        and not step.workdir.is_absolute()
                    ):
                        docker_workdirs.append(str(step.workdir))

                    if not has_docker_enivornment:
                        has_docker_enivornment = True
                        self.prepare_steps.append(
                            add_docker_cleanup_step(
                                name="previous-run",
                                container_name=step.docker_environment.container_name,
                                runtime_tag=step.docker_environment.runtime_tag,
                            ).generate()
                        )
                        self.cleanup_steps.append(
                            add_docker_cleanup_step(
                                name="current-run",
                                container_name=step.docker_environment.container_name,
                                runtime_tag=step.docker_environment.runtime_tag,
                            ).generate()
                        )

                    if docker_config != step.docker_environment:
                        docker_config = step.docker_environment
                        self.prepare_steps.append(
                            add_docker_fetch_step(
                                image_url=step.docker_environment.image_url,
                            ).generate()
                        )
                        # Active step below is on purpose. This will delete the old image and create a tag
                        # for the new image when the user decided to change it
                        self.active_steps.append(
                            add_docker_tag_step(
                                image_url=step.docker_environment.image_url,
                                runtime_tag=step.docker_environment.runtime_tag,
                            ).generate()
                        )
                        docker_config = step.docker_environment
                    self.active_steps.append(step.generate())

                    if step.container_commit:
                        self.active_steps.append(
                            add_docker_commit_step(
                                container_name=step.docker_environment.container_name,
                                runtime_tag=step.docker_environment.runtime_tag,
                                step_name=step.name,
                            ).generate()
                        )
                else:
                    self.active_steps.append(step.generate())

        # Add docker workdirs
        # Doesn't matter which config is used, what is important is to create the workdirs
        # in the volume mount, relative to the base workdir (/home/buildbot),
        if docker_workdirs:
            self.prepare_steps.append(
                add_docker_create_workdirs_step(
                    volume_mount=docker_config.volume_mount,
                    image_url=docker_config.image_url,
                    workdirs=docker_workdirs,
                ).generate()
            )
            

        self.cleanup_steps.append(add_worker_cleanup_step(name="current-run").generate())

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
