import fnmatch

from buildbot.buildrequest import BuildRequest
from buildbot.process.builder import Builder
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from constants import RELEASE_BRANCHES, SAVED_PACKAGE_BRANCHES


def fnmatch_any(branch: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(branch, pattern) for pattern in patterns)

# This function is crucial in build to worker assignment logic.
# It's based on the assumption that the worker has a total_jobs property
# and the builder has a jobs property. Please modify with care.
def canStartBuild(
    builder: Builder, wfb: AbstractWorkerForBuilder, request: BuildRequest
) -> bool:
    """
    Check if the builder can start a build on the given worker for the given request.
    This function checks if the worker has enough jobs available for the builder
    based on the builder's job claim and the total jobs available on the worker.
    Args:
        builder (Builder): The builder instance.
        wfb (AbstractWorkerForBuilder): The worker for the builder instance.
        request (BuildRequest): The build request instance.
    Returns:
        bool: True if the builder can start a build on the worker, False otherwise.
    """
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
    """
    Select the next build request for the builder based on branch priority and submission time.
    Args:
        builder (Builder): The builder instance.
        requests (list[BuildRequest]): A list of build requests for the builder.
    Returns:
        BuildRequest: The next build request to be processed.
    """

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
