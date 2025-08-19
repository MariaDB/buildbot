from collections import defaultdict

from buildbot.plugins import worker
from configuration.workers.base import WorkerBase


class WorkerPool:
    """
    A class to manage a pool of workers categorized by architecture.

    Attributes:
        workers (defaultdict): A dictionary where keys are architecture types (str)
            and values are lists of worker names (str) associated with that architecture.
        instances (list): A list of worker instances.

    Methods:
        __init__():
            Initializes the WorkerPool with empty workers and instances.

        add(arch: str, worker):
            Adds a worker to the pool under the specified architecture.
            Args:
                arch (str): The architecture type to associate the worker with.
                worker (object): The worker object, which must have `name` and `instance` attributes.

        get_workers_for_arch(arch: str, filter_fn: callable = None) -> list:
            Retrieves a list of worker names for the specified architecture, optionally filtered
            by a provided function.
            Args:
                arch (str): The architecture type to retrieve workers for.
                filter_fn (callable, optional): A function to filter the workers. Defaults to None.
            Returns:
                list: A list of worker names matching the specified architecture and filter criteria.
            Raises:
                ValueError: If no workers are found for the specified architecture.
    """

    def __init__(self):
        self.workers = defaultdict(list)

    def add(self, arch, worker):
        self.workers[arch].append((worker))

    def get_instances(self):
        return [
            worker.instance for workers in self.workers.values() for worker in workers
        ]

    def get_workers_for_arch(self, arch: str, filter_fn: str = lambda _: True) -> list:
        workers_for_arch = [worker for worker in self.workers.get(arch, [])]
        workers = list(filter(lambda w: filter_fn(w.name), workers_for_arch))
        if not workers:
            raise ValueError(f"No workers found for architecture: {arch}")
        return workers


class NonLatent(WorkerBase):
    """
    Represents a non-latent worker for the buildbot system.

    This class is responsible for initializing and configuring a worker instance
    with specific properties, including the maximum number of builds and total jobs.

    Attributes:
        instance (worker.Worker): The worker instance created during initialization.
        config (dict[str, dict]): Configuration dictionary containing worker-specific settings.
        max_builds (int): Maximum number of builds the worker can handle concurrently.
        total_jobs (int): Total number of jobs assigned to the worker.

    Args:
        name (str): The name of the worker.
        config (dict[str, dict]): Configuration dictionary containing worker-specific settings.
        total_jobs (int): Total number of jobs assigned to the worker.
        max_builds (int, optional): Maximum number of builds the worker can handle concurrently. Defaults to 999 because the builder-to-worker allocation is handled by canStartBuild() based on how many jobs a builder is requesting.
    """

    def __init__(
        self, name: str, config: dict[str, dict], total_jobs: int, max_builds=999
    ):
        self.instance = None
        self.requested_jobs = 0
        self.builders = {}
        self.config = config
        self.max_builds = max_builds
        self.total_jobs = total_jobs
        super().__init__(name, properties={"total_jobs": total_jobs})
        self.__define()

    def __define(self):
        self.instance = worker.Worker(
            self.name,
            password=self._get_password(),
            max_builds=self.max_builds,
            properties=self.properties,
        )

    def _get_password(self) -> str:
        return self.config["private"]["worker_pass"][self.name]
