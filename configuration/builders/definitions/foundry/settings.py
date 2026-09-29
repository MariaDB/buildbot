import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from configuration.steps.base import StepOptions
from configuration.steps.commands.foundry import (
    BASE_BRANCH_ENV,
    BRANCH_ENV,
    BUILT_PLUGINS_ENV,
    PLUGINS_ENV,
)
from configuration.steps.commands.packages import (
    InstallDEBPackages,
    InstallRPMPackages,
    SetupDEBRepo,
    SetupDEBRepoFromURL,
    SetupRPMRepo,
    SetupRPMRepoFromURL,
)

# Foundry CI settings, and the paths and properties its sequences share; see
# definitions/foundry/README.md. Plugins aren't listed: the dispatcher finds
# them in Foundry.
#
# HOW TO ADD A TARGET
#   1. Add it to RPM_TARGETS, DEB_TARGETS or BINTAR_TARGETS below, named after
#      the MariaDB server builder it mirrors, minus "<arch>-". For
#      amd64-debian-13-deb-autobake and aarch64-debian-13-deb-autobake:
#
#          PackageTarget(
#              "debian-13-deb-autobake",
#              image="debian13",
#              arch=["amd64", "aarch64"],
#              base_image="docker.io/library/debian:13",
#          ),
#
#      Each arch gets a builder, foundry-<arch>-<name>, on the workers that
#      master-migration/master.cfg gives that arch (FOUNDRY_WORKERS_BY_ARCH).
#   2. List it under each MariaDB version below that should build it.
#
# HOW TO ADD A MARIADB VERSION
#   Add it to MARIADB_VERSIONS below, with the targets it builds:
#
#       "11.8": MariaDBVersion(
#           targets=["debian-13-deb-autobake", "rhel-9-rpm-autobake"],
#       ),
#
#   Targets must be on the mirrors for that version. Those only on CI so far
#   go under ci_only instead; a new series not on the mirrors at all has
#   only ci_only.

## ------------------------------------------------------------------- ##
##                              TARGETS                                ##
## ------------------------------------------------------------------- ##


@dataclass
class Target:
    # A platform plugins are built for; see HOW TO ADD A TARGET. Bintar
    # targets are built and tested in image.
    name: str
    image: str  # quay worker image tag, where the plugins are built
    arch: list[str]  # "amd64", "aarch64", or one of ARCH_OVERRIDES


@dataclass
class PackageTarget(Target):
    # An rpm or deb target: its packages are built in image, then installed
    # and tested in base_image, the plain upstream image, so an undeclared
    # dependency fails. base_mounts are bind mounts for base_image.
    base_image: str
    base_mounts: list[tuple[str, str]] = field(default_factory=list)


# UBI reaches the full RHEL repos only through the host's entitlement, so RHEL
# targets must run on RHEL hosts.
RHEL_SUBSCRIPTION_MOUNTS = [
    ("/etc/pki/entitlement", "/run/secrets/etc-pki-entitlement"),
    ("/etc/rhsm", "/run/secrets/rhsm"),
]

RPM_TARGETS = [
    PackageTarget(
        "centos-stream9-rpm-autobake",
        image="centosstream9",
        arch=["amd64", "aarch64"],
        base_image="quay.io/centos/centos:stream9",
    ),
    PackageTarget(
        "centos-stream10-rpm-autobake",
        image="centosstream10",
        arch=["amd64", "aarch64"],
        base_image="quay.io/centos/centos:stream10",
    ),
    PackageTarget(
        "rhel-8-rpm-autobake",
        image="rhel8",
        arch=["amd64", "aarch64"],
        base_image="registry.access.redhat.com/ubi8/ubi",
        base_mounts=RHEL_SUBSCRIPTION_MOUNTS,
    ),
    PackageTarget(
        "rhel-9-rpm-autobake",
        image="rhel9",
        arch=["amd64", "aarch64"],
        base_image="registry.access.redhat.com/ubi9/ubi",
        base_mounts=RHEL_SUBSCRIPTION_MOUNTS,
    ),
    PackageTarget(
        "rhel-10-rpm-autobake",
        image="rhel10",
        arch=["amd64", "aarch64"],
        base_image="registry.access.redhat.com/ubi10/ubi",
        base_mounts=RHEL_SUBSCRIPTION_MOUNTS,
    ),
    PackageTarget(
        "sles-1507-rpm-autobake",
        image="sles1507",
        arch=["amd64"],
        base_image="registry.suse.com/bci/bci-base:15.7",
    ),
    PackageTarget(
        "sles-1600-rpm-autobake",
        image="sles1600",
        arch=["amd64"],
        base_image="registry.suse.com/bci/bci-base:16.0",
    ),
    PackageTarget(
        "opensuse-1600-rpm-autobake",
        image="opensuse1600",
        arch=["amd64"],
        base_image="docker.io/opensuse/leap:16.0",
    ),
]

DEB_TARGETS = [
    PackageTarget(
        "debian-12-deb-autobake",
        image="debian12",
        arch=["amd64", "aarch64", "x86"],
        base_image="docker.io/library/debian:12",
    ),
    PackageTarget(
        "debian-13-deb-autobake",
        image="debian13",
        arch=["amd64", "aarch64"],
        base_image="docker.io/library/debian:13",
    ),
    PackageTarget(
        "ubuntu-2204-deb-autobake",
        image="ubuntu22.04",
        arch=["amd64", "aarch64"],
        base_image="docker.io/library/ubuntu:22.04",
    ),
    PackageTarget(
        "ubuntu-2404-deb-autobake",
        image="ubuntu24.04",
        arch=["amd64", "aarch64"],
        base_image="docker.io/library/ubuntu:24.04",
    ),
    PackageTarget(
        "ubuntu-2604-deb-autobake",
        image="ubuntu26.04",
        arch=["amd64", "aarch64"],
        base_image="docker.io/library/ubuntu:26.04",
    ),
]

# Built against an unpacked server bintar: centos7 up to 11.4, almalinux8
# from 11.8. amd64 only: see mirror_bintar in PACKAGE_TYPES.
BINTAR_TARGETS = [
    Target("centos-7-bintar", image="centos7-bintar", arch=["amd64"]),
    Target("almalinux-8-bintar", image="almalinux8-bintar", arch=["amd64"]),
]

## ------------------------------------------------------------------- ##
##                          MARIADB VERSIONS                           ##
## ------------------------------------------------------------------- ##


@dataclass
class MariaDBVersion:
    # targets: built on every run; each must be on the mirrors for this
    # version. ci_only: on CI but not on the mirrors yet, so built only when
    # Force picks a CI tarbuildnum; move them to targets once a release is
    # mirrored. A version with only ci_only (a new series) is skipped unless
    # Force picks a tarbuildnum, and pull requests skip it.
    targets: list[str] = field(default_factory=list)
    ci_only: list[str] = field(default_factory=list)

    def __post_init__(self):
        known = {t.name for t in RPM_TARGETS + DEB_TARGETS + BINTAR_TARGETS}
        for name in self.targets + self.ci_only:
            if name not in known:
                raise ValueError(
                    f"Unknown Foundry target {name!r}: add it to RPM_TARGETS, "
                    "DEB_TARGETS or BINTAR_TARGETS"
                )
        both = set(self.targets) & set(self.ci_only)
        if both:
            raise ValueError(f"In both targets and ci_only: {sorted(both)}")
        if not (self.targets or self.ci_only):
            raise ValueError("A MariaDB version needs targets or ci_only")


MARIADB_VERSIONS = {
    "11.4": MariaDBVersion(
        targets=[
            "centos-stream9-rpm-autobake",
            "centos-stream10-rpm-autobake",
            "rhel-8-rpm-autobake",
            "rhel-9-rpm-autobake",
            "rhel-10-rpm-autobake",
            "debian-12-deb-autobake",
            "ubuntu-2204-deb-autobake",
            "ubuntu-2404-deb-autobake",
            "centos-7-bintar",
        ],
    ),
    "11.8": MariaDBVersion(
        targets=[
            "centos-stream9-rpm-autobake",
            "centos-stream10-rpm-autobake",
            "rhel-8-rpm-autobake",
            "rhel-9-rpm-autobake",
            "rhel-10-rpm-autobake",
            "sles-1507-rpm-autobake",
            "sles-1600-rpm-autobake",
            "opensuse-1600-rpm-autobake",
            "debian-12-deb-autobake",
            "debian-13-deb-autobake",
            "ubuntu-2204-deb-autobake",
            "ubuntu-2404-deb-autobake",
            "ubuntu-2604-deb-autobake",
            "almalinux-8-bintar",
        ],
    ),
    "12.3": MariaDBVersion(
        targets=[
            "centos-stream9-rpm-autobake",
            "centos-stream10-rpm-autobake",
            "rhel-8-rpm-autobake",
            "rhel-9-rpm-autobake",
            "rhel-10-rpm-autobake",
            "sles-1507-rpm-autobake",
            "sles-1600-rpm-autobake",
            "opensuse-1600-rpm-autobake",
            "debian-12-deb-autobake",
            "debian-13-deb-autobake",
            "ubuntu-2204-deb-autobake",
            "ubuntu-2404-deb-autobake",
            "ubuntu-2604-deb-autobake",
            "almalinux-8-bintar",
        ],
    ),
    # TODO - No action here, this is just an example so we don't forget.
    # A new series, not on the mirrors yet:
    # "13.3": MariaDBVersion(
    #     ci_only=["debian-12-deb-autobake", "rhel-9-rpm-autobake"],
    # ),
}

## ------------------------------------------------------------------- ##
##                          OTHER SETTINGS                             ##
## ------------------------------------------------------------------- ##

# FOUNDRY_REPO_URL in docker-compose/.env (MariaDB/foundry) and .env.dev (a
# fork). The project is its owner/name.
REPO_URL = os.environ["FOUNDRY_REPO_URL"]
REPO_PROJECT = urlparse(REPO_URL).path.strip("/").removesuffix(".git")
REPO_BRANCH = "main"  # built when Force is given no commit

# GitHub usernames allowed to press Force, if MariaDB members.
FORCE_USERS = ["RazvanLiviuVarzaru", "fauust"]

# Where server packages come from: the mirrors (default) or a CI tarbuildnum,
# picked per version on Force. Pull requests always use the mirrors.
CI_URL = "https://ci.mariadb.org"  # TEMPORARY: production CI while dev-only
MIRROR_URL = "https://mirror.mariadb.org"

# Clones Foundry, finds the plugins, archives the commit, triggers the builds.
DISPATCHER_NAME = "foundry-trigger-builders"
DISPATCHER_IMAGE = "debian12"  # only needs git; runs on the amd64 pool

# Arches missing from the multi-arch manifests: image_suffix goes on the
# worker image tag, base_image_prefix replaces the base image's registry, so
# neither shares a local tag with amd64.
ARCH_OVERRIDES = {
    "x86": {
        "image_suffix": "-386",
        "base_image_prefix": "docker.io/i386/",
        "platform": "linux/386",
    },
}

# Per package type, for all its targets.
PACKAGE_TYPES = {
    "rpm": {
        "repo_file": "MariaDB.repo",  # published by the CI server builder
        "galera_repo_suffix": "repo",  # of CI's galera repo file
        "mirror_path": "yum",  # <MIRROR_URL>/yum/<version>/<os>/<os_version>/<arch>/
        "build_packages": ["MariaDB-devel"],
        # MariaDB-test only requires /usr/bin/perl; on SUSE that is perl-base,
        # without the Memoize MTR needs.
        "test_packages": ["MariaDB-server", "MariaDB-test", "perl(Memoize)"],
    },
    "deb": {
        "repo_file": "mariadb.sources",  # published by the CI server builder
        "galera_repo_suffix": "sources",  # of CI's galera repo file
        "mirror_path": "repo",  # <MIRROR_URL>/repo/<version>/<os> <codename> main
        "build_packages": ["libmariadb-dev"],
        "test_packages": ["mariadb-server", "mariadb-test"],
    },
    "bintar": {
        # The only flavour mirrored, hence amd64 only.
        "mirror_bintar": "bintar-linux-systemd-x86_64",
    },
}

## ------------------------------------------------------------------- ##
##       INTERNALS: adding a target or version changes nothing below    ##
## ------------------------------------------------------------------- ##

TARGETS_BY_TYPE = {"rpm": RPM_TARGETS, "deb": DEB_TARGETS, "bintar": BINTAR_TARGETS}

# Foundry's own storage, kept apart from the server's as the connectors' is:
# FOUNDRY_PACKAGES_DIR on the worker hosts, mounted as /packages in Foundry's
# containers, and served by nginx at <ARTIFACTS_URL>/foundry.
PACKAGES_DIR = os.environ["FOUNDRY_PACKAGES_DIR"]
ARTIFACTS_URL = f"{os.environ['ARTIFACTS_URL']}/foundry"

# The Foundry archive for the package builds, one directory per dispatcher
# build, in Foundry's storage.
ARCHIVE = "sources/%(prop:buildnumber)s/foundry-%(prop:foundry_head)s.tar.gz"

# Saved packages and MTR logs, per MariaDB version and server source. Mirror
# builds have no tarbuildnum and go under "mirror" (":~" also catches empty).
RUN_DIR = "%(prop:mariadb_version)s-%(prop:tarbuildnum:~mirror)s"
LOGS_DIR = f"{RUN_DIR}/%(prop:foundry_revision)s/logs/%(prop:buildername)s"
SAVE_LOGS_PATH = f"/packages/{LOGS_DIR}"

SERVER_BINTAR_PROP = "%(prop:server_bintar_dir)s"

# "basename" is a pull request's target branch, set by the GitHub hook.
EVENT_ENV_VARS = [
    (BRANCH_ENV, "%(prop:branch)s"),
    (BASE_BRANCH_ENV, "%(prop:basename:-)s"),
]
MARIADB_VERSION_ENV_VARS = [("MARIADB_VERSION", "%(prop:mariadb_version)s")]
# The plugins the dispatcher asked for, then those that built.
PLUGINS_ENV_VARS = [(PLUGINS_ENV, "%(prop:foundry_plugins)s")]
BUILT_PLUGINS_ENV_VARS = [(BUILT_PLUGINS_ENV, "%(prop:built_plugins)s")]

# A partly successful step is a warning, but still fails the build.
BEST_EFFORT_OPTIONS = StepOptions(flunkOnWarnings=True)

# Per package type: set up the CI repo, set up the mirror repo, install.
PACKAGE_COMMANDS = {
    "DEB": (SetupDEBRepoFromURL, SetupDEBRepo, InstallDEBPackages),
    "RPM": (SetupRPMRepoFromURL, SetupRPMRepo, InstallRPMPackages),
}
