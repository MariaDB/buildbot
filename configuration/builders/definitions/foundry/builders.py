from pathlib import Path

import yaml

from configuration.builders.base import GenericBuilder
from configuration.builders.common import docker_config
from configuration.builders.definitions.foundry import sources
from configuration.builders.sequences.foundry import autobake, dispatcher

with open(Path(__file__).parent / "foundry.yaml") as f:
    _FOUNDRY_CONFIG = yaml.safe_load(f)

_SEQUENCE_BY_PACKAGE_TYPE = {
    "rpm": autobake.rpm,
    "deb": autobake.deb,
}
_REPO_FILE_BY_PACKAGE_TYPE = {
    "rpm": "MariaDB.repo",
    "deb": "mariadb.sources",
}
# MariaDB Server mirrors, used when a version is dispatched without a
# ci.mariadb.org tarbuildnum (sources.MIRROR). The trailing path segment is
# the MariaDB version, which the mirrors publish as a directory of its own
# (e.g. https://mirror.mariadb.org/yum/11.4/) -- see foundry.yaml.
_MIRROR_REPO_URL_BY_PACKAGE_TYPE = {
    "rpm": "https://mirror.mariadb.org/yum/%(prop:mariadb_version)s",
    "deb": "https://mirror.mariadb.org/repo/%(prop:mariadb_version)s",
}
# TEMPORARY: pull the MariaDB-devel/libmariadb-dev repo from production CI
# rather than $ARTIFACTS_URL (dev), to build against real tarballs while this
# pipeline is still dev-only. Revert to os.environ["ARTIFACTS_URL"] once done.
_DEVEL_REPO_ARTIFACTS_URL = "https://ci.mariadb.org"
# x86 worker images are a separate 32-bit tag (e.g. "debian12-386"), not part
# of the amd64/aarch64 multi-arch manifest the other image tags resolve to,
# and need an explicit --platform on pull to fetch that 32-bit variant.
_ARCH_IMAGE_SUFFIX = {"x86": "-386"}
_ARCH_PLATFORM = {"x86": "linux/386"}


FOUNDRY_BUILDERS_BY_ARCH = {}
# Builders grouped by (ops, os version), regardless of arch.
FOUNDRY_BUILDERS_BY_PACKAGE = {}
for package_config in _FOUNDRY_CONFIG["packages"]:
    ops = package_config["ops"]
    version = package_config["version"]
    package = f"{ops}-{version}"
    package_type = package_config["type"]
    for arch in package_config["arch"]:
        image = f"{ops}{version}{_ARCH_IMAGE_SUFFIX.get(arch, '')}"
        platform = _ARCH_PLATFORM.get(arch)
        if package_type == "bintar":
            # Bintar builds link against a MariaDB server bintar (see
            # autobake.bintar) instead of installing -devel packages from an
            # autobake builder's repo, so there's no repo URL to build. Only
            # the CI side needs a builder name -- the mirror bintar is the
            # same tarball for every builder, see DownloadServerBintarFromMirror.
            sequence = autobake.bintar(
                docker_config(image=image, platform=platform),
                package_config["ci_bintar_builder"],
            )
        else:
            sequence_fn = _SEQUENCE_BY_PACKAGE_TYPE[package_type]
            repo_file = _REPO_FILE_BY_PACKAGE_TYPE[package_type]
            # Server autobake builder that publishes
            # MariaDB-devel/libmariadb-dev for this platform, e.g.
            # "amd64-debian-12-deb-autobake" -- see BUILDERS_AUTOBAKE in
            # constants.py.
            autobake_builder = (
                f"{arch}-{package_config['os_info_key']}-{package_type}-autobake"
            )
            repo_file_url = f"{_DEVEL_REPO_ARTIFACTS_URL}/%(prop:tarbuildnum)s/{autobake_builder}/{repo_file}"
            # Both repo sources are wired into every package builder; which
            # one runs is decided per build from the tarbuildnum property.
            sequence = sequence_fn(
                docker_config(image=image, platform=platform),
                repo_file_url,
                _MIRROR_REPO_URL_BY_PACKAGE_TYPE[package_type],
            )
        builder = GenericBuilder(
            name=f"foundry-{arch}-{ops}-{version}",
            sequences=[sequence],
        )
        FOUNDRY_BUILDERS_BY_ARCH.setdefault(arch, []).append(builder)
        FOUNDRY_BUILDERS_BY_PACKAGE.setdefault(package, []).append(builder)

# Supported MariaDB versions and the packages each one builds. Configured in
# configuration/builders/definitions/foundry/foundry.yaml.
FOUNDRY_MARIADB_VERSIONS = _FOUNDRY_CONFIG["mariadb_versions"]
for version_config in FOUNDRY_MARIADB_VERSIONS.values():
    for package in version_config["packages"]:
        assert (
            package in FOUNDRY_BUILDERS_BY_PACKAGE
        ), f"Unknown foundry package: {package}"


# Which builders each Triggerable fires, keyed by scheduler name -- consumed
# by FOUNDRY_TRIGGERABLE_SCHEDULERS in configuration/schedulers/foundry.py.
FOUNDRY_TRIGGERABLE_BUILDERS = {
    sources.scheduler_name(version): [
        builder.name
        for package in version_config["packages"]
        for builder in FOUNDRY_BUILDERS_BY_PACKAGE[package]
    ]
    for version, version_config in FOUNDRY_MARIADB_VERSIONS.items()
}


def _dispatch_specs():
    # One spec per supported MariaDB version, telling _FoundryDispatchStep
    # which force-scheduler fields hold that version's choice and which
    # Triggerable to fire once it has read them.
    return [
        {
            "mariadb_version": version,
            "source_property": sources.source_property(version),
            "tarbuildnum_property": sources.tarbuildnum_property(version),
            "scheduler": sources.scheduler_name(version),
        }
        for version in FOUNDRY_MARIADB_VERSIONS
    ]


# The dispatcher only clones Foundry and reads the plugin list out of it, so
# the image just needs git -- any of the package images will do, and this one
# is already on the amd64 pool the dispatcher runs on.
_DISPATCHER_IMAGE = "debian12"

DISPATCHER_BUILDER = GenericBuilder(
    name="foundry-trigger-builders",
    sequences=[
        dispatcher.trigger_foundry(
            docker_config(image=_DISPATCHER_IMAGE), _dispatch_specs()
        )
    ],
)
