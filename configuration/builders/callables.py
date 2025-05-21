import fnmatch

from buildbot.buildrequest import BuildRequest
from buildbot.process.builder import Builder
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from constants import RELEASE_BRANCHES, SAVED_PACKAGE_BRANCHES


def fnmatch_any(branch: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(branch, pattern) for pattern in patterns)


def canStartBuild(
    builder: Builder, wfb: AbstractWorkerForBuilder, request: BuildRequest
) -> bool:
    reserved_jobs = 0
    total_worker_jobs = wfb.worker.properties[
        "total_jobs"
    ]  # This property (config-time) must exist at worker level
    current_builder_job_claim = builder.config.properties["jobs"]

    if current_builder_job_claim > total_worker_jobs:
        return False

    for (
        bfw
    ) in (
        wfb.worker.workerforbuilders.values()
    ):  # iterate through builders assigned to current worker
        if (
            bfw.isBusy()
        ):  # isBusy means another builder is running on the current worker so we need to calculate how many jobs were claimed
            other_builder_job_claim = bfw.builder.config.properties[
                "jobs"
            ]  # This property (config-time) must exist at Builder level
            reserved_jobs = reserved_jobs + other_builder_job_claim

    available_jobs = total_worker_jobs - reserved_jobs

    if current_builder_job_claim > available_jobs:
        return False

    return True  # True if there are enough jobs for this builder on current worker


def nextBuild(builder: Builder, requests: list[BuildRequest]) -> BuildRequest:
    def build_request_sort_key(request: BuildRequest):
        branch = request.sources[""].branch
        # Booleans are sorted False first.
        # Priority is given to releaseBranches, savePackageBranches
        # then it's first come, first serve.
        return (
            not fnmatch_any(branch, RELEASE_BRANCHES),
            not fnmatch_any(branch, SAVED_PACKAGE_BRANCHES),
            request.getSubmitTime(),
        )

    return min(requests, key=build_request_sort_key)
