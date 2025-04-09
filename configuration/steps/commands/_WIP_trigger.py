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
    def __init__(self, name, schedulername, doStepIf, additional_properties={}):
        self.name = name
        self.schedulername = schedulername
        self.doStepIf = doStepIf
        self.additional_properties = additional_properties

    def generate(self):
        properties = {
            "tarbuildnum": Property("tarbuildnum"),  # set by tarball-docker
            "mariadb_version": Property("mariadb_version"),  # set by tarball-docker
            "master_branch": Property("master_branch"),  # set by tarball-docker
            "parentbuildername": Property("buildername"),  # set by tarball-docker
        }
        properties.update(self.additional_properties)

        return steps.Trigger(
            name=self.name,
            schedulerNames=[self.schedulername],
            waitForFinish=False,  # standard value across buildbot
            updateSourceStamp=False,  # standard value across buildbot
            set_properties=properties,
            doStepIf=self.doStepIf,
        )


class Install(Trigger):
    def __init__(self):
        self.name = "Trigger Install Builders"
        self.schedulername = "s_install"
        self.doStepIf = (
            lambda step: hasInstall(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
            and hasPackagesGenerated(step)
        )

        super().__init__(self.name, self.schedulername, self.doStepIf)


class Upgrade(Trigger):
    def __init__(self):
        self.name = "Trigger Upgrade Builders"
        self.schedulername = "s_upgrade"
        self.doStepIf = (
            lambda step: hasUpgrade(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
            and hasPackagesGenerated(step)
        )

        super().__init__(self.name, self.schedulername, self.doStepIf)


class DockerLibrary(Trigger):
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
