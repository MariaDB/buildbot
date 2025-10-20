import os
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
    processor_set_docker_runtime_environment,
    processor_worker_cleanup,
)
from configuration.workers.base import WorkerBase


class BaseBuilder:
    """
    BaseBuilder is a class responsible for managing build sequences and generating
    build configurations for a Buildbot builder. It provides methods to add build
    sequences, process build steps, and generate a factory and configuration for
    the builder.

    Attributes:
        name (str): The name of the builder.
        build_sequences (list[BuildSequence]): A list of build sequences associated
            with the builder.

    Methods:
        __init__(name: str):
            Initializes the BaseBuilder instance with a name and an empty list of
            build sequences.

        add_sequence(sequence: BuildSequence):
            Adds a build sequence to the builder.

        get_factory() -> BuildFactory:
            Generates and returns a BuildFactory instance containing the processed
            build steps.

        get_config(
            can_start_build: Callable[[Builder, AbstractWorkerForBuilder, BuildRequest], bool],
            Generates and returns a BuilderConfig object for the builder, including
            worker names, tags, build properties, and factory steps.
    """

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

        # Step Pre-Processing
        active_steps = processor_set_docker_runtime_environment(
            builder_name=self.name,
            environment=os.environ["ENVIRON"],
            active_steps=active_steps,
        )

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
        jobs: int,
        next_build: Callable[[Builder, Iterable[BuildRequest]], BuildRequest],
        tags: list[str] = [],
        properties: dict[str, str] = None,
    ) -> util.BuilderConfig:
        """
        Generates a BuilderConfig object for the builder, including worker names,
        tags, build properties, and factory steps.
        Args:
            workers (Iterable[WorkerBase]): An iterable of WorkerBase instances
                representing the workers assigned to this builder.
            can_start_build (Callable): A callable that determines if a build can
                start on a worker.
            jobs (int): The number of CPU's to allocate for commands that support parallel execution.
            next_build (Callable): A callable that determines the next build request.
            tags (list[str], optional): A list of tags associated with the builder.
                Defaults to an empty list.
            properties (dict[str, str], optional): Additional properties for the builder.
                Defaults to an empty dictionary.'
        Mention on the jobs parameter:
            - jobs is a measure of how many CPU's are used for the build, for commands that support parallel execution (e.g. make, mtr).
            - provide a value greater or equal to 1
            - jobs should never exceed the number of CPU's available on the worker, given by the worker total_jobs property.
            - canStartBuild will determine at runtime if the builder can start on any of the workers assigned to it, based on what other jobs were claimed (currently running) by other builders.
        Returns:
            util.BuilderConfig: A BuilderConfig object containing the builder's configuration.
        """
        # Jobs is mandatory, otherwise builder to worker allocation at runtime cannot be done
        assert jobs >= 1, "Jobs must be greater than or equal to 1"
        if not properties:
            properties = {}
        properties["jobs"] = jobs

        # Update worker metadata
        for worker in workers:
            worker.requested_jobs += jobs
            worker.builders[self.name] = jobs
        return util.BuilderConfig(
            name=self.name,
            workernames=[worker.name for worker in workers],
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
