# Where a Foundry run gets its MariaDB server packages, picked per version on
# the force scheduler. The dispatcher turns it into the tarbuildnum property:
# set for CI_TARBALL, unset for MIRROR. No imports, so both the builder
# definitions and the dispatch step can use it.

MIRROR = "Use MariaDB Server mirrors"
CI_TARBALL = "Use a ci.mariadb.org tarball"
SKIP = "Skip this version"

# Dropdown order.
CHOICES = [MIRROR, CI_TARBALL, SKIP]


# A version is on the mirrors once it has targets there. One that isn't yet,
# e.g. a new series, lists its platforms under ci_only only: it builds from a
# CI tarball when asked, and is skipped otherwise.
def on_mirrors(version_config) -> bool:
    # version_config: a settings.MariaDBVersion.
    return bool(version_config.targets)


def choices(mirrored: bool) -> list[str]:
    return CHOICES if mirrored else [CI_TARBALL, SKIP]


def default(mirrored: bool) -> str:
    return MIRROR if mirrored else SKIP


def _slug(mariadb_version: str) -> str:
    # No dots in property and scheduler names.
    return mariadb_version.replace(".", "_")


# Force-scheduler field with this version's choice from CHOICES.
def source_property(mariadb_version: str) -> str:
    return f"foundry_source_{_slug(mariadb_version)}"


# Force-scheduler field with this version's tarbuildnum, for CI_TARBALL.
def tarbuildnum_property(mariadb_version: str) -> str:
    return f"foundry_tarbuildnum_{_slug(mariadb_version)}"


# Triggerable for this version's targets, whatever the source.
def scheduler_name(mariadb_version: str) -> str:
    return f"foundry_{_slug(mariadb_version)}_scheduler"


# Triggerable for this version's ci_only builders, fired on CI_TARBALL only.
def ci_only_scheduler_name(mariadb_version: str) -> str:
    return f"foundry_{_slug(mariadb_version)}_ci_only_scheduler"
