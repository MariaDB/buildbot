from buildbot.plugins import *

from utils import *

def getSchedulers():
    l = []

    l.append(schedulers.Triggerable(name="s_upstream_all",
        builderNames=getBranchBuilderNames))

    schedulerProtectedBranches = schedulers.Triggerable(name="s_protected_branches",
        builderNames=github_status_builders)
    l.append(schedulerProtectedBranches)


    schedulerPackages = schedulers.Triggerable(name="s_packages",
            builderNames=getAutobakeBuilderNames)
    l.append(schedulerPackages)

    schedulerBigtests = schedulers.Triggerable(name="s_bigtest",
            builderNames=getBigtestBuilderNames)
    l.append(schedulerBigtests)

    schedulerInstall = schedulers.Triggerable(name="s_install",
            builderNames=getInstallBuilderNames)
    l.append(schedulerInstall)

    schedulerUpgrade = schedulers.Triggerable(name="s_upgrade",
            builderNames=getUpgradeBuilderNames)
    l.append(schedulerUpgrade)

    schedulerEco = schedulers.Triggerable(name="s_eco",
            builderNames=getEcoBuilderNames)
    l.append(schedulerEco)

    schedulerDockerlibrary = schedulers.Triggerable(name="s_dockerlibrary",
            builderNames=getDockerLibraryNames)
    l.append(schedulerDockerlibrary)

    l.append(schedulers.Triggerable(name="s_wordpress", builderNames=getWordpressNames))

    return l
