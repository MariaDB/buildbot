from configuration.steps.base import StepOptions
from configuration.steps.commands.infra import (
    CleanupDockerResources,
    CleanupWorkerDir,
    ContainerCommit,
    CreateDockerWorkdirs,
    FetchContainerImage,
    TagContainerImage,
)
from configuration.steps.remote import ShellStep


def add_docker_create_workdirs_step(
    volume_mount: str, image_url: str, workdirs: list[str]
) -> ShellStep:
    """
    Create a step to set up Docker work directories.
    This step prepares the necessary directories in a Docker container
    for the build process, ensuring that the specified work directories
    are created and mounted correctly.
    Args:
        volume_mount (str): The volume mount specification for Docker.
        image_url (str): The URL of the Docker image to use.
        workdirs (list[str]): A list of work directories to create in the container.
    Returns:
        ShellStep: A configured ShellStep that executes the CreateDockerWorkdirs command.
    """
    return ShellStep(
        command=CreateDockerWorkdirs(
            volume_mount=volume_mount, image_url=image_url, workdirs=workdirs
        ),
        options=StepOptions(
            haltOnFailure=True,
        ),
    )


def add_docker_cleanup_step(
    name: str, container_name: str, runtime_tag: str
) -> ShellStep:
    """
    Create a step to clean up Docker resources.
    This step removes the specified Docker container and its associated resources
    after the build process is complete, ensuring that no leftover containers
    or images remain.
    Args:
        name (str): The name of the cleanup step.
        container_name (str): The name of the Docker container to clean up.
        runtime_tag (str): The runtime tag for the Docker image.
    Returns:
        ShellStep: A configured ShellStep that executes the CleanupDockerResources command.
    """
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
    """
    Create a step to fetch a Docker container image.
    This step pulls the specified Docker image from a registry, ensuring that
    the required image is available for the build process.
    Args:
        image_url (str): The URL of the Docker image to fetch.
    Returns:
        ShellStep: A configured ShellStep that executes the FetchContainerImage command.
    """
    return ShellStep(
        command=FetchContainerImage(
            image_url=image_url,
        ),
        options=StepOptions(
            haltOnFailure=True,
        ),
    )


def add_docker_tag_step(image_url: str, runtime_tag: str) -> ShellStep:
    """
    Create a step to tag a Docker container image.
    This step applies a runtime tag to the specified Docker image, allowing
    it to be identified and used in subsequent build steps.
    Args:
        image_url (str): The URL of the Docker image to tag.
        runtime_tag (str): The runtime tag to apply to the Docker image.
    Returns:
        ShellStep: A configured ShellStep that executes the TagContainerImage command.
    """
    return ShellStep(
        command=TagContainerImage(
            image_url=image_url,
            runtime_tag=runtime_tag,
        ),
        options=StepOptions(
            haltOnFailure=True,
        ),
    )


def add_docker_commit_step(
    container_name: str, runtime_tag: str, step_name: str, step_options: StepOptions
) -> ShellStep:
    """
    Create a step to commit a Docker container.
    This step commits the current state of a Docker container to a new image,
    allowing the changes made during the build process to be saved and reused.
    Args:
        container_name (str): The name of the Docker container to commit.
        runtime_tag (str): The runtime tag for the new Docker image.
        step_name (str): The name of the step for identification.
    Returns:
        ShellStep: A configured ShellStep that executes the ContainerCommit command.
    """
    return ShellStep(
        command=ContainerCommit(
            container_name=container_name,
            runtime_tag=runtime_tag,
            step_name=step_name,
        ),
        options=step_options,
    )


def add_worker_cleanup_step(name: str) -> ShellStep:
    """
    Create a step to clean up the worker directory.
    This step removes the worker directory used in the current or previous run,
    ensuring that no leftover files or directories remain after the build process.
    Args:
        name (str): The name of the cleanup step.
    Returns:
        ShellStep: A configured ShellStep that executes the CleanupWorkerDir command.
    """
    return ShellStep(
        command=CleanupWorkerDir(name=name),
        options=StepOptions(
            alwaysRun=True,
        ),
    )
