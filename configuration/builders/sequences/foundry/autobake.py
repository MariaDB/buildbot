import os

from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL, BashCommand
from configuration.steps.commands.download import GitInitFromCommit
from configuration.steps.commands.foundry import (
    BUILT_PLUGINS_ENV,
    INSTALLED_PLUGINS_ENV,
    PLUGINS_ENV,
    BuildPlugins,
    DiscoverPluginMTRSuites,
    DownloadServerBintar,
    DownloadServerBintarFromMirror,
    ExtractPluginBintarIntoServerBintar,
    InstallBuiltPackages,
    ListInstalledPlugins,
    ListPluginsWithPackages,
    RunPluginMTRSuite,
    RunPluginMTRSuiteFromBintar,
    SavePluginPackages,
)
from configuration.steps.commands.packages import (
    InstallDEBPackages,
    InstallRPMPackages,
    SetupDEBRepo,
    SetupDEBRepoFromURL,
    SetupRPMRepo,
    SetupRPMRepoFromURL,
)
from configuration.steps.remote import PropFromShellStep, ShellStep

_MARIADB_VERSION_ENV = [("MARIADB_VERSION", "%(prop:mariadb_version)s")]

# The plugins to build come from the dispatcher, which discovers them in the
# Foundry checkout (all of them, or just the ones a pull request touched).
# built/installed narrow that down as the build proceeds -- see the
# best-effort handling in configuration/steps/commands/foundry.py. Passed as
# environment rather than interpolated into the scripts; see PLUGINS_ENV.
_PLUGINS_ENV = [(PLUGINS_ENV, "%(prop:foundry_plugins)s")]
_BUILT_PLUGINS_ENV = [(BUILT_PLUGINS_ENV, "%(prop:built_plugins)s")]
_INSTALLED_PLUGINS_ENV = [(INSTALLED_PLUGINS_ENV, "%(prop:installed_plugins)s")]

# Steps that partly succeed report it in their exit code; the step shows a
# warning you can open to see which plugin failed, and flunkOnWarnings makes
# the build fail anyway so a half-working run is never reported green.
_BEST_EFFORT_OPTIONS = StepOptions(flunkOnWarnings=True)


# Where the MariaDB server packages come from is a per-build decision (made
# per MariaDB version on foundry_force_scheduler, see
# configuration/builders/definitions/foundry/sources.py) rather than a
# per-builder one, so both repo sources are wired into every package builder
# and picked between here. tarbuildnum is the whole signal: the dispatcher
# sets it only for a ci.mariadb.org run, so no tarbuildnum -- including on a
# build of one of these builders that was never given one -- means the
# MariaDB Server mirrors.
def _uses_ci_tarball(step):
    return bool(step.getProperty("tarbuildnum"))


def _uses_mirror(step):
    return not _uses_ci_tarball(step)


# Pull request runs are throwaway validation of a proposed change, not a
# source of packages anyone should be able to install from, so they skip
# saving. Set by the dispatcher, which is the only place that knows whether
# the run came from a GitHub pull request event.
def _not_pull_request(step):
    return not step.getProperty("is_pull_request", False)


# Same reason the two repo steps are conditional: a mirror-sourced build has
# no build number to file its packages and logs under, so it gets its own
# "mirror" bucket instead of an empty path segment. ":~" falls back when the
# property is unset *or* empty.
_SERVER_SOURCE = "%(prop:tarbuildnum:~mirror)s"


def clone_foundry_step(config: DockerConfig, depth: int = 1):
    # depth=0 (full history) is what the dispatcher needs: working out which
    # plugins a pull request touches means diffing against the merge-base
    # with its target branch, which a shallow checkout doesn't have. Foundry
    # is small enough that a full clone costs nothing. The package builders
    # only ever build a single checked-out tree, so they keep depth=1.
    return InContainer(
        ShellStep(
            # revision is always empty on foundry_force_scheduler, so fetch
            # the branch tip instead of a pinned commit. For a pull request
            # the branch is the PR's own refs/pull/<n>/head ref.
            command=GitInitFromCommit(
                repo_url="%(prop:repository)s",
                commit="%(prop:branch)s",
                depth=depth,
            ),
        ),
        docker_environment=config,
    )


def _capture_foundry_revision_step(config: DockerConfig):
    # foundry_force_scheduler never gives us a concrete revision (see
    # clone_foundry_step), so read back the commit that actually got
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
    # save_logs_path saves into on failure -- see foundry.py. One MTR run
    # covers every built plugin's suites, so these logs are per run, with no
    # plugin segment.
    url = (
        f"{os.environ['ARTIFACTS_URL']}/foundry/%(prop:mariadb_version)s-{_SERVER_SOURCE}"
        "/%(prop:foundry_revision)s/logs/%(prop:buildername)s"
    )
    return InContainer(
        ShellStep(command=command, url=URL(url=url, url_text="Logs")),
        docker_environment=config,
    )


def _build_plugins_step(config: DockerConfig, command: BuildPlugins):
    return InContainer(
        ShellStep(
            command=command,
            env_vars=_MARIADB_VERSION_ENV + _PLUGINS_ENV,
            options=_BEST_EFFORT_OPTIONS,
            decode_rc=ShellStep.PARTIAL_SUCCESS_DECODE_RC,
        ),
        docker_environment=config,
    )


def _built_plugins_step(config: DockerConfig):
    # Narrows the requested plugins down to the ones that actually produced
    # a package, so everything downstream works off what exists rather than
    # what was asked for.
    return InContainer(
        PropFromShellStep(
            command=ListPluginsWithPackages(),
            property="built_plugins",
            env_vars=_PLUGINS_ENV,
        ),
        docker_environment=config,
    )


def _save_packages_step(config: DockerConfig):
    # The same builder gets triggered once per mariadb_version (and, on a
    # different run, for a different foundry commit) -- both need to be in
    # the destination path, or a later run silently overwrites an earlier
    # one's saved packages. So does the plugin, since one run now builds
    # several: $plugin is filled in by the shell, per plugin, which is why
    # SavePluginPackages exists rather than a plain SavePackages over the
    # workspace root (run.cmake pools every plugin's packages there).
    # mariadb_version-tarbuildnum is kept as a single segment so it reads
    # unambiguously as "the tarbuildnum for this mariadb_version", not some
    # unrelated build number. Mirror-sourced builds have no tarbuildnum and
    # land under "<version>-mirror" instead -- see _SERVER_SOURCE.
    destination = (
        f"/packages/foundry/%(prop:mariadb_version)s-{_SERVER_SOURCE}/$plugin"
        "/%(prop:foundry_revision)s/%(prop:buildername)s"
    )
    # One link per plugin isn't expressible on a step, so this points at the
    # directory holding all of this run's plugin trees.
    url = f"{os.environ['ARTIFACTS_URL']}/foundry/%(prop:mariadb_version)s-{_SERVER_SOURCE}"
    return InContainer(
        ShellStep(
            command=SavePluginPackages(destination=destination),
            env_vars=_BUILT_PLUGINS_ENV,
            url=URL(url=url, url_text="Packages"),
            options=StepOptions(doStepIf=_not_pull_request),
        ),
        docker_environment=config,
    )


def deb(config: DockerConfig, repo_file_url: str, mirror_repo_url: str):
    sequence = BuildSequence()
    sequence.add_step(clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupDEBRepoFromURL(repo_file_url),
                options=StepOptions(doStepIf=_uses_ci_tarball),
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupDEBRepo(
                    repo_name="mariadb",
                    repo_url=mirror_repo_url,
                    name="Install MariaDB Server mirror repo",
                ),
                options=StepOptions(doStepIf=_uses_mirror),
            ),
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
    sequence.add_step(_build_plugins_step(config, BuildPlugins("DEB")))
    sequence.add_step(_built_plugins_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallBuiltPackages("DEB"),
                env_vars=_BUILT_PLUGINS_ENV,
                options=_BEST_EFFORT_OPTIONS,
                decode_rc=ShellStep.PARTIAL_SUCCESS_DECODE_RC,
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=ListInstalledPlugins("DEB"),
                property="installed_plugins",
                env_vars=_BUILT_PLUGINS_ENV,
            ),
            docker_environment=config,
        )
    )
    # Before mariadb-test lands: it ships plugin suites of its own under the
    # same layout, which would be indistinguishable from ours afterwards.
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverPluginMTRSuites("DEB"),
                property="plugin_suites",
                env_vars=_INSTALLED_PLUGINS_ENV,
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(_save_packages_step(config))
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


def rpm(config: DockerConfig, repo_file_url: str, mirror_repo_url: str):
    sequence = BuildSequence()
    sequence.add_step(clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupRPMRepoFromURL(repo_file_url),
                options=StepOptions(doStepIf=_uses_ci_tarball),
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupRPMRepo(
                    repo_name="mariadb",
                    repo_url=mirror_repo_url,
                    name="Install MariaDB Server mirror repo",
                ),
                options=StepOptions(doStepIf=_uses_mirror),
            ),
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
    sequence.add_step(_build_plugins_step(config, BuildPlugins("RPM")))
    sequence.add_step(_built_plugins_step(config))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallBuiltPackages("RPM"),
                env_vars=_BUILT_PLUGINS_ENV,
                options=_BEST_EFFORT_OPTIONS,
                decode_rc=ShellStep.PARTIAL_SUCCESS_DECODE_RC,
            ),
            docker_environment=config,
            container_commit=True,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=ListInstalledPlugins("RPM"),
                property="installed_plugins",
                env_vars=_BUILT_PLUGINS_ENV,
            ),
            docker_environment=config,
        )
    )
    # Before MariaDB-test lands: it ships plugin suites of its own under the
    # same layout, which would be indistinguishable from ours afterwards.
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverPluginMTRSuites("RPM"),
                property="plugin_suites",
                env_vars=_INSTALLED_PLUGINS_ENV,
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(_save_packages_step(config))
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
    # against a matching MariaDB server bintar via -DCMAKE_PREFIX_PATH.
    # Testing then means unpacking the plugin's own bintar into that same
    # server bintar tree and running its bundled ./mtr, rather than
    # installing MariaDB-server/MariaDB-test as system packages.
    #
    # Same split as the deb/rpm sequences: the CI bintar comes from
    # ci_bintar_builder on production CI (e.g. "amd64-centos-7-bintar"), the
    # mirror one from the newest GA release of this MariaDB version. Only one
    # of the two runs, and whichever does sets server_bintar_dir.
    sequence = BuildSequence()
    sequence.add_step(clone_foundry_step(config))
    sequence.add_step(_capture_foundry_revision_step(config))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DownloadServerBintar(ci_bintar_builder),
                property="server_bintar_dir",
                options=StepOptions(doStepIf=_uses_ci_tarball),
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DownloadServerBintarFromMirror(),
                property="server_bintar_dir",
                options=StepOptions(doStepIf=_uses_mirror),
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(
        _build_plugins_step(config, BuildPlugins(cmake_prefix_path=_SERVER_BINTAR_PROP))
    )
    sequence.add_step(_built_plugins_step(config))
    sequence.add_step(_save_packages_step(config))
    # There is no install step here, so built is as far as the plugin list
    # gets narrowed -- the extraction takes each built plugin's tarball from
    # its own <plugin>.build/.
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=ExtractPluginBintarIntoServerBintar(_SERVER_BINTAR_PROP),
                property="plugin_suites",
                env_vars=_BUILT_PLUGINS_ENV,
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
