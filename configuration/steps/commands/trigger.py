from twisted.internet import defer

from buildbot.plugins import steps
from buildbot.process.buildstep import BuildStepFailed
from buildbot.process.properties import Interpolate, Property
from buildbot.steps.trigger import Trigger as BuildbotTrigger
from configuration.builders.definitions.foundry import sources
from constants import SAVED_PACKAGE_BRANCHES
from utils import (
    hasDockerLibrary,
    hasInstall,
    hasPackagesGenerated,
    hasUpgrade,
    savePackageIfBranchMatch,
)


class Trigger:
    def __init__(self, name, schedulername, doStepIf, properties=None):
        self.name = name
        self.schedulername = schedulername
        self.doStepIf = doStepIf
        self.properties = properties or {}

    def generate(self):
        return steps.Trigger(
            name=self.name,
            schedulerNames=[self.schedulername],
            waitForFinish=False,  # standard value across buildbot
            updateSourceStamp=False,  # standard value across buildbot
            set_properties=self.properties,
            doStepIf=self.doStepIf,
        )


class Server(Trigger):
    def __init__(self, name, schedulername, doStepIf, additional_properties=None):
        properties = {
            "tarbuildnum": Property("tarbuildnum"),  # set by tarball-docker
            "mariadb_version": Property("mariadb_version"),  # set by tarball-docker
            "master_branch": Property("master_branch"),  # set by tarball-docker
            "parentbuildername": Property("buildername"),  # set by tarball-docker
        }
        if additional_properties:
            properties.update(additional_properties)
        super().__init__(name, schedulername, doStepIf, properties)


class ConODBC(Trigger):
    def __init__(self):
        self.name = "Trigger Conc-ODBC Builders"
        self.schedulername = "conc_odbc_all_scheduler"
        self.doStepIf = lambda step: True
        properties = {
            "tarbuildnum": Property(
                "buildnumber"
            ),  # Used by get_tarball.sh to identify the tarball dir on CI
            "mariadb_version": "ci",  # Used by get_tarball.sh to download ci.tar.gz
            "odbc_to_mariadb_repo": Property("odbc_to_mariadb_repo"),
            "odbc_version": Property("odbc_version"),
        }

        super().__init__(self.name, self.schedulername, self.doStepIf, properties)


class ConCPP(Trigger):
    def __init__(self):
        self.name = "Trigger Conc-CPP Builders"
        self.schedulername = "conc_cpp_all_scheduler"
        self.doStepIf = lambda step: True
        properties = {
            "tarbuildnum": Property(
                "buildnumber"
            ),  # Used by get_tarball.sh to identify the tarball dir on CI
            "mariadb_version": "ci",  # Used by get_tarball.sh to download ci.tar.gz
            "cpp_to_mariadb_repo": Property("cpp_to_mariadb_repo"),
            "cpp_version": Property("cpp_version"),
        }

        super().__init__(self.name, self.schedulername, self.doStepIf, properties)


class ConC(Trigger):
    def __init__(self):
        self.name = "Trigger Conc-C Builders"
        self.schedulername = "conc_c_all_scheduler"
        self.doStepIf = lambda step: True
        properties = {
            "tarbuildnum": Property(
                "buildnumber"
            ),  # Used by get_tarball.sh to identify the tarball dir on CI
            "mariadb_version": "ci",  # Used by get_tarball.sh to download ci.tar.gz
        }

        super().__init__(self.name, self.schedulername, self.doStepIf, properties)


class _FoundryDispatchStep(BuildbotTrigger):
    # Merged with Trigger's own renderables, in buildbot 2.x and 3.0+ alike.
    renderables = ["source_url"]

    def __init__(self, mariadb_versions, ci_url, source_url, **kwargs):
        self.mariadb_versions = mariadb_versions
        self.ci_url = ci_url
        self.source_url = source_url
        super().__init__(**kwargs)

    def _prop(self, name: str) -> str:
        return str(self.getProperty(name, "") or "").strip()

    # Fans out per MariaDB version, with properties read from this build: the
    # version's force-scheduler choices (see sources.py), and what the earlier
    # steps found.
    @defer.inlineCallbacks
    def getSchedulersAndProperties(self):
        plugins = self._prop("foundry_plugins")
        branch = self._prop("branch")
        # Pull requests always use the mirrors and save no packages.
        is_pull_request = branch.startswith("refs/pull/")
        commit = self._prop("foundry_head")
        # What the package builds need to get Foundry: see dispatcher.py.
        foundry_source = {
            "foundry_revision": self._prop("foundry_revision"),
            "foundry_source_url": self.source_url,
            "foundry_source_sha256": self._prop("foundry_source_sha256"),
        }
        schedulers_and_properties = []
        # Spelled out in a log: a skipped version leaves no other trace.
        plan = []
        errors = []

        event = "pull request" if is_pull_request else "force build"
        header = [f"event:   {event}", f"commit:  {commit or '(unknown)'} ({branch})"]

        if not plugins:
            # E.g. a pull request touching no plugin: a pass, not a failure.
            yield self.addCompleteLog(
                "dispatch plan",
                "\n".join(header + ["No plugins to build -- nothing triggered"]) + "\n",
            )
            return []

        missing = [name for name, value in foundry_source.items() if not value]
        if missing:
            errors.append(
                f"no Foundry source to hand on, missing: {', '.join(missing)}"
            )

        for version, version_config in self.mariadb_versions.items():
            mirrored = sources.on_mirrors(version_config)
            if is_pull_request:
                if not mirrored:
                    plan.append(f"{version}: skipped, not on the mirrors yet")
                    continue
                source = sources.MIRROR
                tarbuildnum = ""
            else:
                source = self.getProperty(
                    sources.source_property(version), sources.default(mirrored)
                )
                tarbuildnum = self._prop(sources.tarbuildnum_property(version))

            allowed = sources.choices(mirrored)
            if source not in allowed:
                # Only reachable through a hand-edited rebuild.
                errors.append(
                    f"{version}: package source {source!r} isn't available -- "
                    f"expected one of {', '.join(repr(c) for c in allowed)}"
                )
                continue

            if source == sources.SKIP:
                plan.append(f"{version}: skipped, no builders triggered")
                continue

            if source == sources.CI_TARBALL and not tarbuildnum:
                errors.append(
                    f"{version}: set to '{sources.CI_TARBALL}' but no tarbuildnum "
                    "was given -- supply one, or pick "
                    + " or ".join(repr(c) for c in allowed if c != sources.CI_TARBALL)
                    + " instead"
                )
                continue

            properties = {
                "mariadb_version": version,
                "foundry_plugins": plugins,
                "is_pull_request": is_pull_request,
                # The dispatcher's build number, for the status report.
                "foundry_run": self.getProperty("buildnumber"),
                **foundry_source,
            }
            if source == sources.CI_TARBALL:
                # Set only for CI: the package builders take its absence to
                # mean the mirrors.
                properties["tarbuildnum"] = tarbuildnum
                plan.append(f"{version}: {self.ci_url}/{tarbuildnum}/")
            else:
                plan.append(f"{version}: MariaDB Server mirrors")

            # A version not on the mirrors has no targets, so no Triggerable
            # for them.
            if mirrored:
                schedulers_and_properties.append(
                    (sources.scheduler_name(version), properties)
                )
            if version_config.ci_only:
                # Not on the mirrors yet, so only built from a CI tarball.
                ci_only = ", ".join(version_config.ci_only)
                if source == sources.CI_TARBALL:
                    schedulers_and_properties.append(
                        (sources.ci_only_scheduler_name(version), properties)
                    )
                    also = "also " if mirrored else ""
                    plan.append(f"{version}: {also}CI-only targets: {ci_only}")
                else:
                    plan.append(f"{version}: skipped CI-only targets: {ci_only}")

        lines = [*header, f"plugins: {plugins}", *plan]
        if errors:
            lines += ["", "Nothing was triggered:", *errors]
        yield self.addCompleteLog("dispatch plan", "\n".join(lines) + "\n")
        if errors:
            # Only after the log, as BuildStepFailed carries no message, and
            # before anything is triggered.
            raise BuildStepFailed()
        # For the status report: the builders it should find, and each
        # version's server source, "<version>=<tarbuildnum or mirror>".
        self.setProperty(
            "foundry_triggered",
            " ".join(scheduler for scheduler, _ in schedulers_and_properties),
            self.name,
        )
        self.setProperty(
            "foundry_sources",
            " ".join(
                f"{props['mariadb_version']}={props.get('tarbuildnum', 'mirror')}"
                for _, props in schedulers_and_properties
            ),
            self.name,
        )
        return schedulers_and_properties


class FoundryDispatch:
    def __init__(
        self, mariadb_versions, scheduler_names: list[str], ci_url: str, source_url: str
    ):
        # mariadb_versions: settings.MARIADB_VERSIONS. scheduler_names:
        # every Triggerable the step may pick. source_url: the Foundry
        # archive's URL, an Interpolate string.
        self.mariadb_versions = mariadb_versions
        self.scheduler_names = scheduler_names
        self.ci_url = ci_url
        self.source_url = source_url

    def generate(self):
        return _FoundryDispatchStep(
            mariadb_versions=self.mariadb_versions,
            ci_url=self.ci_url,
            source_url=Interpolate(self.source_url),
            name="Trigger Foundry Builders",
            schedulerNames=sorted(self.scheduler_names),
            # Fail with any package build, so the pull request status does
            # too. The waiting build holds a job, so the next run queues.
            waitForFinish=True,
            updateSourceStamp=False,
        )


class Install(Server):
    def __init__(self):
        self.name = "Trigger Install Builders"
        self.schedulername = "s_install"
        self.doStepIf = (
            lambda step: hasInstall(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
            and hasPackagesGenerated(step)
        )

        super().__init__(self.name, self.schedulername, self.doStepIf)


class Upgrade(Server):
    def __init__(self):
        self.name = "Trigger Upgrade Builders"
        self.schedulername = "s_upgrade"
        self.doStepIf = (
            lambda step: hasUpgrade(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
            and hasPackagesGenerated(step)
        )

        super().__init__(self.name, self.schedulername, self.doStepIf)


class DockerLibrary(Server):
    def __init__(self, RHEL):
        self.name = "Trigger DockerLibrary Builder"
        self.schedulername = "s_dockerlibrary"
        self.doStepIf = lambda step: hasDockerLibrary(step)
        self.additional_properties = {}
        if RHEL:
            self.additional_properties = {
                "ubi": "-ubi",
                "GH_WORKFLOW": "test-image-ubi.yml",
            }

        super().__init__(
            self.name, self.schedulername, self.doStepIf, self.additional_properties
        )
