from configuration.steps.base import BaseStep
from configuration.steps.infra import (
    add_docker_create_workdirs_step,
    add_docker_cleanup_step,
    add_docker_fetch_step,
    add_docker_tag_step,
    add_docker_commit_step,
    add_worker_cleanup_step
)
from configuration.builders.infra.runtime import InContainer


def processor_docker_workdirs(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    docker_workdirs = []

    for step in active_steps:
        if isinstance(step, InContainer):
            if (
                str(step.workdir) not in docker_workdirs
                and not step.workdir.is_absolute()
            ):
                docker_workdirs.append(str(step.workdir))

    prepare_steps.append(
        add_docker_create_workdirs_step(
            volume_mount=step.docker_environment.volume_mount,
            image_url=step.docker_environment.image_url,
            workdirs=docker_workdirs,
        )
    )

    return prepare_steps, active_steps, cleanup_steps

def processor_docker_cleanup(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    for step in active_steps:
        if isinstance(step, InContainer):
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

def processor_docker_commit(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    for id, step in enumerate(active_steps):
        if isinstance(step, InContainer):
            if step.container_commit:
                active_steps.insert(
                    id + 1,
                    add_docker_commit_step(
                        container_name=step.docker_environment.container_name,
                        runtime_tag=step.docker_environment.runtime_tag,
                        step_name=step.name,
                    )
                )

    return prepare_steps, active_steps, cleanup_steps

def processor_docker_tag(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    current_docker_environment = None

    for id, step in enumerate(active_steps):
        if isinstance(step, InContainer):
            # Changing environments requires deleting the old image/tag and creating a new one
            if current_docker_environment != step.docker_environment:
                active_steps.insert(
                    id - 1,
                    add_docker_tag_step(
                        image_url=step.docker_environment.image_url,
                        runtime_tag=step.docker_environment.runtime_tag,
                    )
                )
                current_docker_environment = step.docker_environment

    return prepare_steps, active_steps, cleanup_steps

def processor_docker_fetch(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()
    current_docker_environment = None

    for step in active_steps:
        if isinstance(step, InContainer):
            if current_docker_environment != step.docker_environment:
                prepare_steps.append(
                    add_docker_fetch_step(
                        image_url=step.docker_environment.image_url,
                    )
                )
                current_docker_environment = step.docker_environment

    return prepare_steps, active_steps, cleanup_steps

def processor_worker_cleanup(prepare_steps: list[BaseStep], active_steps: list[BaseStep], cleanup_steps: list[BaseStep]) -> tuple[list[BaseStep], list[BaseStep], list[BaseStep]]:
    prepare_steps = prepare_steps.copy()
    active_steps = active_steps.copy()
    cleanup_steps = cleanup_steps.copy()

    prepare_steps.append(
        add_worker_cleanup_step(name="previous-run"))
    cleanup_steps.append(
        add_worker_cleanup_step(name="current-run"))

    return prepare_steps, active_steps, cleanup_steps