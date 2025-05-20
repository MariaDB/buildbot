from configuration.steps.commands.infra import CreateDockerWorkdirs, CleanupDockerResources,FetchContainerImage,TagContainerImage, ContainerCommit, CleanupWorkerDir
from configuration.steps.remote import ShellStep
from configuration.steps.base import StepOptions


def add_docker_create_workdirs_step(volume_mount: str, image_url: str, workdirs: list[str]) -> ShellStep:
    return ShellStep(
        command=CreateDockerWorkdirs(
            volume_mount = volume_mount,
            image_url = image_url,
            workdirs=workdirs),
        options = StepOptions(
            haltOnFailure=True,
        ),
        )

def add_docker_cleanup_step(name: str, container_name: str, runtime_tag: str) -> ShellStep:
    return ShellStep(
        command=CleanupDockerResources(
            name=name,
            container_name=container_name,
            runtime_tag=runtime_tag,
        ),
        options=StepOptions(
            alwaysRun=True,
        ),
        )

def add_docker_fetch_step(image_url: str) -> ShellStep:
    return ShellStep(
        command=FetchContainerImage(
            image_url=image_url,
        ),
        options=StepOptions(
            haltOnFailure=True,)
        )

def add_docker_tag_step(image_url: str, runtime_tag: str) -> ShellStep:
    return ShellStep(
        command=TagContainerImage(
            image_url=image_url,
            runtime_tag=runtime_tag,
        ),
        options=StepOptions(
            haltOnFailure=True,)
        )

def add_docker_commit_step(container_name: str, runtime_tag: str, step_name: str) -> ShellStep:
    return ShellStep(
        command=ContainerCommit(
            container_name=container_name,
            runtime_tag=runtime_tag,
            step_name=step_name,
        ),
        options=StepOptions(
            haltOnFailure=True,)
        )

def add_worker_cleanup_step(name: str) -> ShellStep:
    return ShellStep(
        command=CleanupWorkerDir(name=name),
        options=StepOptions(
            alwaysRun=True,
        ),
    )   