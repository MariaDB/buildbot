from typing import Iterable, Callable
from abc import ABC, abstractmethod

from buildbot.interfaces import IBuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.builder import Builder
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from buildbot.plugins import util

from workers.base import BaseWorker


class BuildSequence(ABC):
    # Steps that will be called at the beginning of the BaseBuilder's build
    # process.
    @abstractmethod
    def get_prepare_steps(self) -> Iterable[IBuildStep]:
        ...

    # Generate steps that will be called after *all* prepare steps for all
    # attached build sequences are called.
    @abstractmethod
    def get_active_steps(self) -> Iterable[IBuildStep]:
        ...

    # Steps that will be called at the end of the BaseBuilder's build process.
    @abstractmethod
    def get_cleanup_steps(self) -> Iterable[IBuildStep]:
        ...


class BaseBuilder:
    def __init__(self, name: str):
        self.name = name
        self.build_sequences: list[BuildSequence] = []

    def add_sequence(self, sequence: BuildSequence):
        self.build_sequences.append(sequence)

    def get_factory(self) -> BuildFactory:
        factory = BuildFactory()
        for seq in self.build_sequences:
            factory.addSteps(seq.get_prepare_steps())

        for seq in self.build_sequences:
            factory.addSteps(seq.get_active_steps())

        # Reverse cleanup, last in, first out.
        for seq in reversed(self.build_sequences):
            factory.addSteps(seq.get_cleanup_steps())

        return factory

    def get_config(
        self,
        workers: Iterable[BaseWorker],
        can_start_build: Callable[
            [Builder, AbstractWorkerForBuilder, BuildRequest], bool],
        next_build: Callable[[Builder, Iterable[BuildRequest]], BuildRequest],
        tags: list[str] = [],
    ) -> util.BuilderConfig:
        return util.BuilderConfig(
            name=self.name,
            workernames=[worker.name for worker in workers],
            tags=tags,
            nextBuild=next_build,
            canStartBuild=can_start_build,
            factory=self.get_factory()
        )
