from buildbot.plugins import schedulers, util

from constants import (builders_autobake, builders_big, builders_dockerlibrary,
                       builders_eco, builders_install, builders_upgrade,
                       builders_wordpress, github_status_builders,
                       supportedPlatforms)


####### SCHEDULER HELPER FUNCTIONS
@util.renderer
def getBranchBuilderNames(props):
    mBranch = props.getProperty("master_branch")

    builders = list(
        filter(lambda x: x not in github_status_builders, supportedPlatforms[mBranch])
    )

    return builders


@util.renderer
def getProtectedBuilderNames(props):
    mBranch = props.getProperty("master_branch")

    builders = list(
        filter(lambda x: x in supportedPlatforms[mBranch], github_status_builders)
    )

    return builders


@util.renderer
def getAutobakeBuilderNames(props):
    builderName = props.getProperty("parentbuildername")
    for b in builders_autobake:
        if builderName in b:
            return [b]
    return []


@util.renderer
def getBigtestBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    for b in builders_big:
        if builderName in b:
            return [b]
    return []


@util.renderer
def getInstallBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    for b in builders_install:
        if builderName in b:
            builders = [b]
            if "rhel" in builderName:
                builders.append(b.replace("rhel", "almalinux"))
            return builders
    return []


@util.renderer
def getUpgradeBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    builds = []
    for b in builders_upgrade:
        if builderName in b:
            if "rhel" in builderName:
                builds.append(b.replace("rhel", "almalinux"))
            builds.append(b)
    return builds


@util.renderer
def getEcoBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    builds = []
    for b in builders_eco:
        if builderName in b:
            builds.append(b)
    return builds


@util.renderer
def getDockerLibraryNames(props):
    return builders_dockerlibrary[0]


@util.renderer
def getWordpressNames(props):
    return builders_wordpress[0]



def getSchedulers():
    l = []

    l.append(
        schedulers.Triggerable(
            name="s_upstream_all", builderNames=getBranchBuilderNames
        )
    )

    schedulerProtectedBranches = schedulers.Triggerable(
        name="s_protected_branches", builderNames=getProtectedBuilderNames
    )
    l.append(schedulerProtectedBranches)

    schedulerPackages = schedulers.Triggerable(
        name="s_packages", builderNames=getAutobakeBuilderNames
    )
    l.append(schedulerPackages)

    schedulerBigtests = schedulers.Triggerable(
        name="s_bigtest", builderNames=getBigtestBuilderNames
    )
    l.append(schedulerBigtests)

    schedulerInstall = schedulers.Triggerable(
        name="s_install", builderNames=getInstallBuilderNames
    )
    l.append(schedulerInstall)

    schedulerUpgrade = schedulers.Triggerable(
        name="s_upgrade", builderNames=getUpgradeBuilderNames
    )
    l.append(schedulerUpgrade)

    schedulerEco = schedulers.Triggerable(name="s_eco", builderNames=getEcoBuilderNames)
    l.append(schedulerEco)

    schedulerDockerlibrary = schedulers.Triggerable(
        name="s_dockerlibrary", builderNames=getDockerLibraryNames
    )
    l.append(schedulerDockerlibrary)

    l.append(schedulers.Triggerable(name="s_wordpress", builderNames=getWordpressNames))

    l.append(
        schedulers.Triggerable(name="s_release_prep", builderNames=["release-prep"])
    )

    l.append(
        schedulers.Triggerable(name="s_jepsen", builderNames=["amd64-ubuntu-2204-jepsen-mysql"])
    )

    return l
