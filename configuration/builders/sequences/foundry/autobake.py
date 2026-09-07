import os

from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.commands.base import URL, BashCommand
from configuration.steps.commands.download import GitInitFromCommit
from configuration.steps.commands.foundry import (
    BuildPlugin,
    DiscoverPluginMTRSuites,
    DownloadServerBintar,
    ExtractPluginBintarIntoServerBintar,
    InstallBuiltPackages,
    RunPluginMTRSuite,
    RunPluginMTRSuiteFromBintar,
)
from configuration.steps.commands.packages import (
    InstallDEBPackages,
    InstallRPMPackages,
    SavePackages,
    SetupDEBRepoFromURL,
    SetupRPMRepoFromURL,
)
from configuration.steps.remote import PropFromShellStep, ShellStep

_MARIADB_VERSION_ENV = [("MARIADB_VERSION", "%(prop:mariadb_version)s")]


def _clone_foundry_step(config: DockerConfig):
    return InContainer(
        ShellStep(
            # revision is always empty on foundry_force_scheduler, so fetch
            # the branch tip instead of a pinned commit.
            command=GitInitFromCommit(
                repo_url="%(prop:repository)s",
                commit="%(prop:branch)s",
            ),
        ),
        docker_environment=config,
    )


def _capture_foundry_revision_step(config: DockerConfig):
    # foundry_force_scheduler never gives us a concrete revision (see
    # _clone_foundry_step), so read back the commit that actually got
    # checked out -- needed to tell apart saved packages built from
    # different foundry/plugin source revisions.
    return InContainer(
        PropFromShellStep(
            command=BashCommand(cmd="git rev-parse --short HEAD"),
            property="foundry_revision",
        ),
        docker_environment=config,
    )


def _run_plugin_mtr_suite_step(config: DockerConfig, command: RunPluginMTRSuite):
    # Points at the same "logs" dir RunPluginMTRSuite's default
    # save_logs_path saves into on failure -- see foundry.py.
    url = (
        f"{os.environ['ARTIFACTS_URL']}/foundry/%(prop:mariadb_version)s-%(prop:tarbuildnum)s"
        "/%(prop:plugin)s/%(prop:foundry_revision)s/logs/%(prop:buildername)s"
    )
    return InContainer(
        ShellStep(command=command, url=URL(url=url, url_text="Logs")),
        docker_environment=config,
    )


def _save_packages_step(config: DockerConfig, package_glob: str):
    # The same builder gets triggered once per mariadb_version (and, on a
    # different run, for a different plugin, or a different foundry commit)
    # -- all three need to be in the destination path, or a later run
    # silently overwrites an earlier one's saved packages.
    # mariadb_version-tarbuildnum is kept as a single segment so it reads
    # unambiguously as "the tarbuildnum for this mariadb_version", not some
    # unrelated build number.
    destination = (
        "/packages/foundry/%(prop:mariadb_version)s-%(prop:tarbuildnum)s/%(prop:plugin)s"
        "/%(prop:foundry_revision)s/%(prop:buildername)s"
    )
    url = (
        f"{os.environ['ARTIFACTS_URL']}/foundry/%(prop:mariadb_version)s-%(prop:tarbuildnum)s"
        "/%(prop:plugin)s/%(prop:foundry_revision)s/%(prop:buildername)s"
    )
    return InContainer(
        ShellStep(
            command=SavePackages(packages=[package_glob], destination=destination),
            url=URL(url=url, url_text="Packages"),
        ),
        docker_environment=config,
    )


def deb(config: DockerConfig, repo_file_url: str):
    sequence = BuildSequence()
    sequence.add_step(_clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(command=SetupDEBRepoFromURL(repo_file_url)),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=InstallDEBPackages(packages=["libmariadb-dev"])),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=BuildPlugin("DEB"), env_vars=_MARIADB_VERSION_ENV),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverPluginMTRSuites("DEB"),
                property="plugin_suites",
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=InstallBuiltPackages("DEB")),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(_save_packages_step(config, "*.deb"))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallDEBPackages(packages=["mariadb-server", "mariadb-test"])
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        _run_plugin_mtr_suite_step(
            config, RunPluginMTRSuite("DEB", "%(prop:plugin_suites)s")
        )
    )
    return sequence


def rpm(config: DockerConfig, repo_file_url: str):
    sequence = BuildSequence()
    sequence.add_step(_clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(command=SetupRPMRepoFromURL(repo_file_url)),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=InstallRPMPackages(packages=["MariaDB-devel"])),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=BuildPlugin("RPM"), env_vars=_MARIADB_VERSION_ENV),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverPluginMTRSuites("RPM"),
                property="plugin_suites",
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(command=InstallBuiltPackages("RPM")),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(_save_packages_step(config, "*.rpm"))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallRPMPackages(packages=["MariaDB-server", "MariaDB-test"])
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        _run_plugin_mtr_suite_step(
            config, RunPluginMTRSuite("RPM", "%(prop:plugin_suites)s")
        )
    )
    return sequence


_SERVER_BINTAR_PROP = "%(prop:server_bintar_dir)s"


def bintar(config: DockerConfig, ci_bintar_builder: str):
    # Bintar images (centos7, almalinux8) have no autobake builder of their
    # own to install -devel packages from -- instead, the plugin is built
    # against a matching MariaDB server bintar (published by ci_bintar_builder
    # on production CI, e.g. "amd64-centos-7-bintar") via -DCMAKE_PREFIX_PATH.
    # Testing then means unpacking the plugin's own bintar into that same
    # server bintar tree and running its bundled ./mtr, rather than
    # installing MariaDB-server/MariaDB-test as system packages.
    sequence = BuildSequence()
    sequence.add_step(_clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DownloadServerBintar(ci_bintar_builder),
                property="server_bintar_dir",
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=BuildPlugin(cmake_prefix_path=_SERVER_BINTAR_PROP),
                env_vars=_MARIADB_VERSION_ENV,
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(_save_packages_step(config, "mariadb-plugin-*.tar.gz"))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=ExtractPluginBintarIntoServerBintar(_SERVER_BINTAR_PROP),
                property="plugin_suites",
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=RunPluginMTRSuiteFromBintar(
                    _SERVER_BINTAR_PROP, "%(prop:plugin_suites)s"
                )
            ),
            docker_environment=config,
        )
    )
    return sequence
