from typing import Callable, Iterable

from buildbot.plugins import util
from buildbot.process.builder import Builder
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.factory import BuildFactory
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from configuration.builders.infra.runtime import BuildSequence
from configuration.steps.processors import (
    processor_docker_cleanup,
    processor_docker_commit,
    processor_docker_fetch,
    processor_docker_tag,
    processor_docker_workdirs,
    processor_worker_cleanup,
)
from configuration.workers.base import WorkerBase


class BaseBuilder:
    def __init__(self, name: str):
        self.name = name
        self.build_sequences: list[BuildSequence] = []

    def add_sequence(self, sequence: BuildSequence):
        self.build_sequences.append(sequence)

    def get_factory(self) -> BuildFactory:
        factory = BuildFactory()

        prepare_steps = []
        active_steps = []
        cleanup_steps = []

        POST_PROCESSING_FUNCTIONS = [
            processor_worker_cleanup,
            processor_docker_cleanup,
            processor_docker_fetch,
            processor_docker_workdirs,
            processor_docker_tag,
            processor_docker_commit,
        ]

        # Get steps from all sequences
        for seq in self.build_sequences:
            active_steps.extend(seq.get_steps())

        # Step Post-Processing
        for func in POST_PROCESSING_FUNCTIONS:
            prepare_steps, active_steps, cleanup_steps = func(
                prepare_steps,
                active_steps,
                cleanup_steps,
            )
        # // end of Post-Processing

        # Generating factory steps
        steps = prepare_steps + active_steps + cleanup_steps
        factory.addSteps(step.generate() for step in steps)

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
