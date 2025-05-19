from collections import defaultdict

from buildbot.interfaces import IWorker
from buildbot.plugins import worker
from configuration.workers.base import WorkerBase


class WorkerPool:
    def __init__(self):
        self.workers = defaultdict(list)
        self.instances = []

    def add(self, arch, worker):
        self.workers[arch].append(worker.name)
        self.instances.append(worker.instance)

    def get_workers_for_arch(self, arch: str, filter_fn: str = None) -> list:
        result = list(filter(filter_fn, self.workers[arch]))
        if not result:
            raise ValueError(f"No workers found for architecture: {arch}")
        return result


class NonLatent(WorkerBase):
    def __init__(
        self, name: str, config: dict[str, dict], total_jobs: int, max_builds=999
    ):
        self.instance = None
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
