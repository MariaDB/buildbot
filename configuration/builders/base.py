from abc import ABC, abstractmethod
from typing import Callable, Iterable

from buildbot.interfaces import IBuildStep
from buildbot.plugins import util
from buildbot.process.builder import Builder
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.factory import BuildFactory
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from configuration.builders.infra.runtime import BuildSequence
from configuration.workers.base import WorkerBase


class BaseBuilder:
    def __init__(self, name: str):
        self.name = name
        self.build_sequences: list[BuildSequence] = []

    def add_sequence(self, sequence: BuildSequence):
        self.build_sequences.append(sequence)

    def get_factory(self) -> BuildFactory:
        factory = BuildFactory()
        # Prevent duplicate preparation and cleanup steps
        seen = set()

        # Preparation steps
        for seq in self.build_sequences:
            for step in seq.get_prepare_steps():
                if step.name not in seen:
                    factory.addStep(step)
                    seen.add(step.name)

        # Active steps
        for seq in self.build_sequences:
            factory.addSteps(seq.get_active_steps())

        # Cleanup steps, in reverse, last in, first out
        for seq in reversed(self.build_sequences):
            for step in seq.get_cleanup_steps():
                if step.name not in seen:
                    factory.addStep(step)
                    seen.add(step.name)

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
