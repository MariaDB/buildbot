from configuration.builders.definitions.foundry.settings import (
    ARCHIVE,
    ARTIFACTS_URL,
    EVENT_ENV_VARS,
    PACKAGES_DIR,
    RUN_DIR,
)
from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands import trigger
from configuration.steps.commands.base import URL, BashCommand
from configuration.steps.commands.download import GitInitFromCommit
from configuration.steps.commands.foundry import (
    ArchiveFoundrySource,
    DiscoverFoundryPlugins,
    WriteFoundryReport,
)
from configuration.steps.remote import PropFromShellStep, ShellStep
from git_auth import git_auth_env_vars


def _clone_foundry_step(config: DockerConfig):
    return InContainer(
        ShellStep(
            # The forced commit, else the webhook's (a PR's head when it was
            # pushed, which the status is reported on, even if the PR has
            # moved on since), else the branch tip. Full history, to diff a PR
            # against its merge base.
            command=GitInitFromCommit(
                repo_url="%(prop:repository)s",
                commit="%(prop:foundry_commit:~%(prop:revision:~%(prop:branch)s)s)s",
                depth=0,
            ),
            # GitHub answers anonymous clones with a 401; see git_auth.py.
            secret_env_vars=git_auth_env_vars(),
        ),
        docker_environment=config,
    )


def _property_step(
    config: DockerConfig,
    command,
    property: str,
    env_vars=None,
    secret_env_vars=None,
    options=None,
):
    return InContainer(
        PropFromShellStep(
            command=command,
            property=property,
            env_vars=env_vars,
            secret_env_vars=secret_env_vars,
            options=options,
        ),
        docker_environment=config,
    )


def _has_plugins(step):
    return bool(step.getProperty("foundry_plugins"))


def trigger_foundry(
    config: DockerConfig,
    mariadb_versions,
    scheduler_names: list[str],
    ci_url: str,
    report_builders: dict,
):
    # The only Foundry clone of a run: it finds the plugins to build and
    # archives the commit, which every package build then downloads. So they
    # all build the same commit, however late they start. report_builders:
    # see WriteFoundryReport. The rest is for trigger.FoundryDispatch.
    sequence = BuildSequence()
    # The run's directory in Foundry's storage, the only part of it the run's
    # containers mount; see settings.RUN_DIR. Made by the containers' user, in
    # a container that runs only mkdir.
    sequence.add_step(
        ShellStep(
            command=BashCommand(
                name="Create run directory",
                cmd=(
                    "docker run --rm -u buildbot "
                    f"--mount type=bind,src={PACKAGES_DIR}/,dst=/storage "
                    f"{config.image_url} mkdir -p /storage/{RUN_DIR}"
                ),
            )
        )
    )
    sequence.add_step(_clone_foundry_step(config))
    # The commit, and its short form.
    sequence.add_step(
        _property_step(config, BashCommand(cmd="git rev-parse HEAD"), "foundry_head")
    )
    sequence.add_step(
        _property_step(
            config, BashCommand(cmd="git rev-parse --short HEAD"), "foundry_revision"
        )
    )
    # Fetches a PR's base branch, so it needs the token too.
    sequence.add_step(
        _property_step(
            config,
            DiscoverFoundryPlugins(),
            "foundry_plugins",
            env_vars=EVENT_ENV_VARS,
            secret_env_vars=git_auth_env_vars(),
        )
    )
    # Nothing to publish when there is nothing to build.
    sequence.add_step(
        _property_step(
            config,
            ArchiveFoundrySource(archive=f"/packages/{ARCHIVE}"),
            "foundry_source_sha256",
            options=StepOptions(doStepIf=_has_plugins),
        )
    )
    sequence.add_step(
        trigger.FoundryDispatch(
            mariadb_versions,
            scheduler_names,
            ci_url,
            source_url=f"{ARTIFACTS_URL}/{ARCHIVE}",
        )
    )
    # Once the package builds are done, whatever their result.
    sequence.add_step(
        InContainer(
            ShellStep(
                command=WriteFoundryReport(
                    f"/packages/{RUN_DIR}", report_builders, ci_url
                ),
                url=URL(
                    url=f"{ARTIFACTS_URL}/{RUN_DIR}/status.html", url_text="Status"
                ),
                options=StepOptions(
                    alwaysRun=True, haltOnFailure=False, doStepIf=_has_plugins
                ),
                warn_on_fail=True,
            ),
            docker_environment=config,
        )
    )
    return sequence
