from buildbot.interfaces import IProperties
from buildbot.plugins import schedulers, util
from constants import (
    BUILDERS_AUTOBAKE,
    BUILDERS_DOCKERLIBRARY,
    BUILDERS_ECO,
    BUILDERS_INSTALL,
    BUILDERS_UPGRADE,
    BUILDERS_WORDPRESS,
    GITHUB_STATUS_BUILDERS,
    SUPPORTED_PLATFORMS,
)


############################
# SCHEDULER HELPER FUNCTIONS
############################
@util.renderer
def branchBuilders(props: IProperties) -> list[str]:
    mBranch = props.getProperty("master_branch")

    builders = list(
        filter(lambda x: x not in GITHUB_STATUS_BUILDERS, SUPPORTED_PLATFORMS[mBranch])
    )

    return builders


@util.renderer
def protectedBranchBuilders(props: IProperties) -> list[str]:
    mBranch = props.getProperty("master_branch")

    builders = list(
        filter(lambda x: x in SUPPORTED_PLATFORMS[mBranch], GITHUB_STATUS_BUILDERS)
    )

    return builders


@util.renderer
def autobakeBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    for b in BUILDERS_AUTOBAKE:
        if builder_name in b:
            return [b]
    return []


@util.renderer
def installBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    for b in BUILDERS_INSTALL:
        if builder_name in b:
            builders = [b]
            if "rhel" in builder_name:
                builders.append(b.replace("rhel", "almalinux"))
                builders.append(b.replace("rhel", "rockylinux"))
            return builders
    return []


@util.renderer
def upgradeBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    builders = []
    for b in BUILDERS_UPGRADE:
        if builder_name in b:
            if "rhel" in builder_name:
                builders.append(b.replace("rhel", "almalinux"))
                builders.append(b.replace("rhel", "rockylinux"))
            builders.append(b)
    return builders


@util.renderer
def ecoBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    builders = []
    for b in BUILDERS_ECO:
        if builder_name in b:
            builders.append(b)
    return builders


@util.renderer
def dockerLibraryBuilders(props: IProperties) -> list[str]:
    return BUILDERS_DOCKERLIBRARY[0]


@util.renderer
def wordpressBuilders(props: IProperties) -> list[str]:
    return BUILDERS_WORDPRESS[0]


SCHEDULERS = [
    schedulers.Triggerable(name="s_upstream_all", builderNames=branchBuilders),
    schedulers.Triggerable(
        name="s_protected_branches", builderNames=protectedBranchBuilders
    ),
    schedulers.Triggerable(name="s_packages", builderNames=autobakeBuilders),
    schedulers.Triggerable(name="s_install", builderNames=installBuilders),
    schedulers.Triggerable(name="s_upgrade", builderNames=upgradeBuilders),
    schedulers.Triggerable(name="s_eco", builderNames=ecoBuilders),
    schedulers.Triggerable(name="s_dockerlibrary", builderNames=dockerLibraryBuilders),
    schedulers.Triggerable(name="s_wordpress", builderNames=wordpressBuilders),
    schedulers.Triggerable(name="s_release_prep", builderNames=["release-prep"]),
    schedulers.Triggerable(
        name="s_jepsen", builderNames=["amd64-ubuntu-2204-jepsen-mariadb"]
    ),
]
