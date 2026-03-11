from buildbot.plugins import steps
from buildbot.process.properties import Property
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
        }

        super().__init__(self.name, self.schedulername, self.doStepIf, properties)


class ConCPP(Trigger):
    def __init__(self):
        self.name = "Trigger Conc-CPP Builders"
        self.schedulername = "conc_cpp_all_scheduler"
        self.doStepIf = lambda step: True
        super().__init__(self.name, self.schedulername, self.doStepIf)


class ConC(Trigger):
    def __init__(self):
        self.name = "Trigger Conc-C Builders"
        self.schedulername = "conc_c_all_scheduler"
        self.doStepIf = lambda step: True

        super().__init__(self.name, self.schedulername, self.doStepIf)


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
