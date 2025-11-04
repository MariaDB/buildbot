from configuration.builders.infra.runtime import InContainer
from configuration.steps.base import BaseStep
from configuration.steps.infra import (
    add_docker_cleanup_step,
    add_docker_commit_step,
    add_docker_create_workdirs_step,
    add_docker_fetch_step,
    add_docker_tag_step,
    add_worker_cleanup_step,
)


def processor_docker_workdirs(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Prepare Docker work directories for steps that require them.
    This function checks the active steps for any InContainer steps and adds a
    Docker work directory creation step for each unique work directory used in those steps.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    docker_workdirs = []
    docker_config = None

    relevant_steps = filter(lambda x: isinstance(x, InContainer), active_steps)
    for step in relevant_steps:
        if str(step.workdir) not in docker_workdirs and not step.workdir.is_absolute():
            docker_workdirs.append(str(step.workdir))
            if not docker_config:
                docker_config = step.docker_environment

    if docker_config:
        prepare_steps.append(
            add_docker_create_workdirs_step(
                volume_mount=docker_config.volume_mount,
                image_url=docker_config.image_url,
                workdirs=docker_workdirs,
            )
        )

    return prepare_steps, active_steps, cleanup_steps


def processor_docker_cleanup(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Prepare Docker cleanup steps for the current and previous runs.
    This function checks the active steps for any InContainer steps and adds cleanup
    steps for the Docker containers used in those steps. It ensures that the cleanup
    steps are added for both the current run and the previous run.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    relevant_steps = filter(lambda x: isinstance(x, InContainer), active_steps)
    for step in relevant_steps:
        cleanup_steps.append(
            add_docker_cleanup_step(
                name="current-run",
                container_name=step.docker_environment.container_name,
                runtime_tag=step.docker_environment.runtime_tag,
            )
        )
        prepare_steps.append(
            add_docker_cleanup_step(
                name="previous-run",
                container_name=step.docker_environment.container_name,
                runtime_tag=step.docker_environment.runtime_tag,
            )
        )
        break

    return prepare_steps, active_steps, cleanup_steps


def processor_docker_commit(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Prepare Docker commit steps for active InContainer steps.
    This function checks the active steps for any InContainer steps that require
    committing the container state and adds a Docker commit step for each such step.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    for id, step in enumerate(active_steps):
        if not isinstance(step, InContainer):
            continue
        if step.container_commit:
            active_steps.insert(
                id + 1,
                add_docker_commit_step(
                    container_name=step.docker_environment.container_name,
                    runtime_tag=step.docker_environment.runtime_tag,
                    step_name=step.name,
                    step_options=step.options,
                ),
            )

    return prepare_steps, active_steps, cleanup_steps


def processor_docker_tag(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Prepare Docker tagging steps for active InContainer steps.
    This function checks the active steps for any InContainer steps and adds a
    tag step whenever an environment change (different docker config) is detected.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    current_docker_environment = None

    for id, step in enumerate(active_steps):
        if not isinstance(step, InContainer):
            continue
            # Changing environments requires deleting the old image/tag and creating a new one
        if current_docker_environment != step.docker_environment:
            active_steps.insert(
                id,
                add_docker_tag_step(
                    image_url=step.docker_environment.image_url,
                    runtime_tag=step.docker_environment.runtime_tag,
                ),
            )
            current_docker_environment = step.docker_environment

    return prepare_steps, active_steps, cleanup_steps


def processor_docker_fetch(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Fetch Docker images for steps that require them.
    This function checks the active steps for any InContainer steps and adds a
    Docker fetch step for each unique Docker environment used in those steps.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    docker_environments = set()

    relevant_steps = filter(lambda x: isinstance(x, InContainer), active_steps)
    for step in relevant_steps:
        if step.docker_environment not in docker_environments:
            prepare_steps.append(
                add_docker_fetch_step(
                    image_url=step.docker_environment.image_url,
                    platform=step.docker_environment.platform,
                )
            )
            docker_environments.add(step.docker_environment)

    return prepare_steps, active_steps, cleanup_steps


def processor_worker_cleanup(
    prepare_steps: list[BaseStep],
    active_steps: list[BaseStep],
    cleanup_steps: list[BaseStep],
) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    """Prepare worker cleanup steps for the current and previous runs.
    This function adds cleanup steps for the worker used in the current and previous runs.
    Args:
        prepare_steps (list[BaseStep]): Steps to be executed before the main steps.
        active_steps (list[BaseStep]): Main steps to be executed.
        cleanup_steps (list[BaseStep]): Steps to be executed after the main steps.
    Returns:
        tuple: Updated lists of prepare_steps, active_steps, and cleanup_steps.
    """
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    prepare_steps.append(add_worker_cleanup_step(name="previous-run"))
    cleanup_steps.append(add_worker_cleanup_step(name="current-run"))

    return prepare_steps, active_steps, cleanup_steps


def processor_set_docker_runtime_environment(
    builder_name: str, active_steps: list[BaseStep], environment: str
) -> None:
    """Set the Docker runtime environment for InContainer steps.
    This function updates the Docker environment for all InContainer steps in the
    active steps, setting the container name to the builder name.
    Args:
        builder_name (str): The name of the builder to set as the container name.
        active_steps (list[BaseStep]): The list of active steps to update.
    Returns:
        list[BaseStep]: The updated list of active steps with the Docker environment set.
    """
    for step in active_steps:
        if isinstance(step, InContainer):
            step.docker_environment._container_name = builder_name
            if environment == "DEV":
                step.docker_environment._container_name = f"dev_{builder_name}"

    return active_steps
