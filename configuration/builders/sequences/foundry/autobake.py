import shlex

from configuration.builders.definitions.foundry.settings import (
    ARTIFACTS_URL,
    BEST_EFFORT_OPTIONS,
    BUILT_PLUGINS_ENV_VARS,
    LOGS_DIR,
    MARIADB_VERSION_ENV_VARS,
    PACKAGE_COMMANDS,
    PLUGINS_ENV_VARS,
    RUN_DIR,
    SAVE_LOGS_PATH,
    SERVER_BINTAR_PROP,
)
from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL
from configuration.steps.commands.foundry import (
    BuildPlugins,
    BuildPluginsShellCommand,
    DiscoverPluginMTRSuites,
    DownloadFoundrySource,
    DownloadServerBintar,
    DownloadServerBintarFromMirror,
    ExtractPluginBintarIntoServerBintar,
    InstallBuiltPackages,
    PrepareBaseImage,
    RunPluginMTRSuite,
    RunPluginMTRSuiteFromBintar,
    SavePluginPackages,
)
from configuration.steps.remote import PropFromShellStep, ShellStep


# The server source is chosen per build: the dispatcher sets tarbuildnum for
# ci.mariadb.org and leaves it unset for the mirrors. Both steps are wired in.
def _uses_ci_tarball(step):
    return bool(step.getProperty("tarbuildnum"))


def _uses_mirror(step):
    return not _uses_ci_tarball(step)


def _not_pull_request(step):
    return not step.getProperty("is_pull_request", False)


# A plugin without MTR suites is only built and installed. With none at all,
# the test steps are skipped.
def _has_suites(step):
    return bool(step.getProperty("plugin_suites"))


def _download_foundry_step(config: DockerConfig):
    # The dispatcher's archive of Foundry; see dispatcher.py.
    return InContainer(
        ShellStep(
            command=DownloadFoundrySource(
                url="%(prop:foundry_source_url)s",
                sha256="%(prop:foundry_source_sha256)s",
            ),
        ),
        docker_environment=config,
    )


def _run_mtr_step(config: DockerConfig, command):
    # One MTR run covers every plugin, so logs are per run.
    return InContainer(
        ShellStep(
            command=command,
            url=URL(url=f"{ARTIFACTS_URL}/{LOGS_DIR}", url_text="Logs"),
            options=StepOptions(doStepIf=_has_suites),
        ),
        docker_environment=config,
    )


def _build_plugins_step(config: DockerConfig, command: BuildPlugins):
    # Also sets built_plugins, which the later steps work off.
    return InContainer(
        ShellStep(
            command=command,
            env_vars=MARIADB_VERSION_ENV_VARS + PLUGINS_ENV_VARS,
            options=BEST_EFFORT_OPTIONS,
            step_class=BuildPluginsShellCommand,
        ),
        docker_environment=config,
    )


def _save_packages_step(config: DockerConfig):
    # One directory per plugin, commit and builder, so runs don't overwrite
    # each other. The link can only point at the run's directory.
    destination = (
        f"/packages/{RUN_DIR}/$plugin/%(prop:foundry_revision)s/%(prop:buildername)s"
    )
    return InContainer(
        ShellStep(
            command=SavePluginPackages(destination=destination),
            env_vars=BUILT_PLUGINS_ENV_VARS,
            url=URL(url=f"{ARTIFACTS_URL}/{RUN_DIR}", url_text="Packages"),
            options=StepOptions(doStepIf=_not_pull_request),
        ),
        docker_environment=config,
    )


def _server_repo_steps(
    package_type: str,
    config: DockerConfig,
    repo_file_url: str,
    mirror_repo_url: str,
    galera_repo_url: str,
    where: str,
):
    # where: "worker" or "base".
    setup_from_url, setup_mirror, _ = PACKAGE_COMMANDS[package_type]
    return [
        InContainer(
            ShellStep(
                # The CI repo has no galera-4, which MariaDB-server needs, so
                # add CI's galera repo too, as rpm-install.sh does. The
                # mirrors carry galera already.
                command=setup_from_url(
                    repo_file_url,
                    galera_repo_url,
                    name=f"Add server CI repo ({where})",
                ),
                options=StepOptions(doStepIf=_uses_ci_tarball),
            ),
            docker_environment=config,
            container_commit=True,
        ),
        InContainer(
            ShellStep(
                command=setup_mirror(
                    repo_name="mariadb",
                    repo_url=mirror_repo_url,
                    name=f"Add server mirror repo ({where})",
                ),
                options=StepOptions(doStepIf=_uses_mirror),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    ]


def packages(
    package_type: str,
    config: DockerConfig,
    base_config: DockerConfig,
    repo_file_url: str,
    mirror_repo_url: str,
    galera_repo_url: str,
    build_packages: list[str],
    test_packages: list[str],
):
    # package_type: "RPM" or "DEB". Built in the worker image (config), then
    # installed and tested in the plain base image (base_config), so an
    # undeclared dependency fails. Only the workspace volume carries over.
    _, _, install = PACKAGE_COMMANDS[package_type]
    # Names from settings.PACKAGE_TYPES, quoted for the shell: an rpm capability such as
    # perl(Memoize) has parentheses. The install commands don't quote, for globs.
    build_packages = [shlex.quote(package) for package in build_packages]
    test_packages = [shlex.quote(package) for package in test_packages]
    sequence = BuildSequence()

    # Build, in the worker image.
    sequence.add_step(_download_foundry_step(config))
    for step in _server_repo_steps(
        package_type, config, repo_file_url, mirror_repo_url, galera_repo_url, "worker"
    ):
        sequence.add_step(step)
    sequence.add_step(
        InContainer(
            ShellStep(
                command=install(
                    packages=build_packages, name="Install build dependencies"
                )
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(_build_plugins_step(config, BuildPlugins(package_type)))
    sequence.add_step(_save_packages_step(config))

    # Install and test, in the base image.
    sequence.add_step(
        InContainer(
            ShellStep(command=PrepareBaseImage()),
            docker_environment=base_config,
            container_commit=True,
        )
    )
    for step in _server_repo_steps(
        package_type,
        base_config,
        repo_file_url,
        mirror_repo_url,
        galera_repo_url,
        "base",
    ):
        sequence.add_step(step)
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallBuiltPackages(package_type),
                env_vars=BUILT_PLUGINS_ENV_VARS,
                options=BEST_EFFORT_OPTIONS,
                decode_rc=ShellStep.PARTIAL_SUCCESS_DECODE_RC,
            ),
            docker_environment=base_config,
            container_commit=True,
        )
    )
    # Before MariaDB-test lands, as its own suites look like ours.
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverPluginMTRSuites(package_type),
                property="plugin_suites",
                env_vars=BUILT_PLUGINS_ENV_VARS,
            ),
            docker_environment=base_config,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=install(packages=test_packages, name="Install test packages"),
                options=StepOptions(doStepIf=_has_suites),
            ),
            docker_environment=base_config,
            container_commit=True,
        )
    )
    sequence.add_step(
        _run_mtr_step(
            base_config,
            RunPluginMTRSuite(
                package_type, "%(prop:plugin_suites)s", save_logs_path=SAVE_LOGS_PATH
            ),
        )
    )
    return sequence


def bintar(
    config: DockerConfig, ci_bintar_url: str, mirror_url: str, mirror_bintar: str
):
    # No -devel packages here: build against a server bintar, from CI or the
    # newest mirrored release, then test inside it with its own MTR.
    sequence = BuildSequence()
    sequence.add_step(_download_foundry_step(config))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DownloadServerBintar(ci_bintar_url),
                property="server_bintar_dir",
                options=StepOptions(doStepIf=_uses_ci_tarball),
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DownloadServerBintarFromMirror(mirror_url, mirror_bintar),
                property="server_bintar_dir",
                options=StepOptions(doStepIf=_uses_mirror),
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        _build_plugins_step(config, BuildPlugins(cmake_prefix_path=SERVER_BINTAR_PROP))
    )
    sequence.add_step(_save_packages_step(config))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=ExtractPluginBintarIntoServerBintar(SERVER_BINTAR_PROP),
                property="plugin_suites",
                env_vars=BUILT_PLUGINS_ENV_VARS,
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        _run_mtr_step(
            config,
            RunPluginMTRSuiteFromBintar(
                SERVER_BINTAR_PROP,
                "%(prop:plugin_suites)s",
                save_logs_path=SAVE_LOGS_PATH,
            ),
        )
    )
    return sequence
