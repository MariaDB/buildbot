from buildbot.interfaces import IProperties
from buildbot.plugins import schedulers, util
from constants import (
    builders_autobake,
    builders_big,
    builders_dockerlibrary,
    builders_eco,
    builders_install,
    builders_upgrade,
    builders_wordpress,
    github_status_builders,
    supportedPlatforms,
)


############################
# SCHEDULER HELPER FUNCTIONS
############################
@util.renderer
def branchBuilders(props: IProperties) -> list[str]:
    master_branch = props.getProperty("master_branch")
    builders = supportedPlatforms[master_branch]
    return list(filter(lambda x: x not in github_status_builders, builders))


@util.renderer
def protectedBranchBuilders(props: IProperties) -> list[str]:
    master_branch = props.getProperty("master_branch")
    builders = supportedPlatforms[master_branch]
    return list(filter(lambda x: x in builders, github_status_builders))


@util.renderer
def autobakeBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    for b in builders_autobake:
        if builder_name in b:
            return [b]
    return []


@util.renderer
def bigtestBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    for b in builders_big:
        if builder_name in b:
            return [b]
    return []


@util.renderer
def installBuilders(props: IProperties) -> list[str]:
    builder_name = props.getProperty("parentbuildername")
    for b in builders_install:
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
    for b in builders_upgrade:
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
    for b in builders_eco:
        if builder_name in b:
            builders.append(b)
    return builders


@util.renderer
def dockerLibraryBuilders(props: IProperties) -> list[str]:
    return builders_dockerlibrary[0]


@util.renderer
def wordpressBuilders(props: IProperties) -> list[str]:
    return builders_wordpress[0]


SCHEDULERS = [
    schedulers.Triggerable(name="s_upstream_all", builderNames=branchBuilders),
    schedulers.Triggerable(
        name="s_protected_branches", builderNames=protectedBranchBuilders
    ),
    schedulers.Triggerable(name="s_packages", builderNames=autobakeBuilders),
    schedulers.Triggerable(name="s_bigtest", builderNames=bigtestBuilders),
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
