"""Where a foundry build gets its MariaDB server packages from.

Picked per supported MariaDB version on foundry_force_scheduler (see
configuration/schedulers/foundry.py) and acted on by the dispatcher's
_FoundryDispatchStep (configuration/steps/commands/trigger.py), which turns
the choice into the "tarbuildnum" property the package builders branch on:
set to a ci.mariadb.org build number for CI_TARBALL, left unset for MIRROR.

Deliberately a leaf module with no imports of its own -- both the dispatch
step (under configuration/steps/) and the foundry builder definitions need
this vocabulary, and those two already import each other transitively.
"""

MIRROR = "Use MariaDB Server mirrors"
CI_TARBALL = "Use a ci.mariadb.org tarball"
SKIP = "Skip this version"

# Order is the order the dropdown renders in; the first entry is also the
# default, i.e. a version nobody touched builds against the mirrors.
CHOICES = [MIRROR, CI_TARBALL, SKIP]
DEFAULT = MIRROR


def _slug(mariadb_version: str) -> str:
    # Property and scheduler names are matched literally in URLs and in the
    # force-scheduler form, so keep the dots out of them.
    return mariadb_version.replace(".", "_")


def source_property(mariadb_version: str) -> str:
    """Force-scheduler field holding this version's choice from CHOICES."""
    return f"foundry_source_{_slug(mariadb_version)}"


def tarbuildnum_property(mariadb_version: str) -> str:
    """Force-scheduler field holding this version's ci.mariadb.org tarbuildnum.

    Only meaningful when the matching source_property is CI_TARBALL.
    """
    return f"foundry_tarbuildnum_{_slug(mariadb_version)}"


def scheduler_name(mariadb_version: str) -> str:
    """Triggerable that runs this version's builders.

    One per version, not per (version, source): MIRROR and CI_TARBALL run the
    same builders and differ only in the tarbuildnum property they carry.
    Which packages a version builds at all is its "packages" list in
    foundry.yaml, and that list has to hold only packages the mirrors publish
    for that version -- see the notes there.
    """
    return f"foundry_{_slug(mariadb_version)}_scheduler"
