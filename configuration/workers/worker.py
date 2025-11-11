from collections import defaultdict

from buildbot.plugins import worker
from configuration.workers.base import WorkerBase


class WorkerPool:
    """
    Manages a pool of workers categorized by architecture.
    This class allows adding workers and retrieving them based on criteria such as architecture, names, and OS type.
    Attributes:
        workers (defaultdict): A dictionary mapping architectures to lists of WorkerBase instances.
    Methods:
        add(worker: WorkerBase): Adds a worker
        get_instances() -> list: Retrieves all worker instances in the pool.
        get_workers_for_arch(arch: str, names: list = None, os_type: str = None) -> list: Retrieves workers for a specific architecture, optionally filtering by names and OS type.
    """

    def __init__(self):
        self.workers = defaultdict(list)

    def add(self, worker: WorkerBase):
        self.workers[worker.arch].append((worker))

    def get_instances(self):
        return [
            worker.instance for workers in self.workers.values() for worker in workers
        ]

    def get_workers_for_arch(
        self, arch: str, names: list = None, os_type: str = None
    ) -> list:
        WorkerPool._raise_for_invalid_os_type(os_type=os_type)
        WorkerPool._raise_for_invalid_arch(arch=arch)

        workers_for_arch: WorkerBase = [worker for worker in self.workers.get(arch, [])]
        if names:
            workers_for_arch = [w for w in workers_for_arch if w.name in names]
        if os_type:
            workers_for_arch = [w for w in workers_for_arch if w.os_type == os_type]

        if not workers_for_arch:
            raise ValueError(
                f"No workers found for: arch={arch}, names={names}, os_type={os_type}"
            )
        return workers_for_arch

    @staticmethod
    def _raise_for_invalid_os_type(os_type: str):
        if os_type and os_type not in WorkerBase.ALLOWED_OS_TYPES:
            raise ValueError(
                f"Invalid OS type: {os_type} requested. Allowed: {WorkerBase.ALLOWED_OS_TYPES}"
            )

    @staticmethod
    def _raise_for_invalid_arch(arch: str):
        if arch not in WorkerBase.ALLOWED_ARCHS:
            raise ValueError(
                f"Invalid arch: {arch} requested. Allowed: {WorkerBase.ALLOWED_ARCHS}"
            )


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
        self,
        name: str,
        config: dict[str, dict],
        os_type: str,
        arch: str,
        total_jobs: int,
        max_builds=999,
    ):
        self.instance = None
        self.requested_jobs = 0
        self.builders = {}
        self.config = config
        self.max_builds = max_builds
        self.total_jobs = total_jobs
        super().__init__(
            name, properties={"total_jobs": total_jobs}, os_type=os_type, arch=arch
        )
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
