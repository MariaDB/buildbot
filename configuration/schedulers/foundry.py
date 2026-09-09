from buildbot.plugins import schedulers, util

import configuration.builders.definitions.foundry.builders as foundry_builders
from configuration.builders.definitions.foundry import sources

FOUNDRY_REPO_URL = "https://github.com/MariaDB/foundry"


def _server_source_parameters():
    # Two fields per supported MariaDB version (see foundry.yaml): where its
    # MariaDB server packages come from, and -- only read when that says
    # sources.CI_TARBALL -- which ci.mariadb.org build to take them from.
    # Left alone, a version builds against the MariaDB Server mirrors.
    parameters = []
    for version in foundry_builders.FOUNDRY_MARIADB_VERSIONS:
        parameters.append(
            util.ChoiceStringParameter(
                name=sources.source_property(version),
                label=f"MariaDB {version}: server packages",
                choices=sources.CHOICES,
                default=sources.DEFAULT,
            )
        )
        parameters.append(
            util.StringParameter(
                name=sources.tarbuildnum_property(version),
                # Kept free of angle brackets and quotes -- buildbot renders
                # parameter labels into the force dialog as HTML.
                label=(
                    f"MariaDB {version}: ci.mariadb.org tarbuildnum "
                    "(required by, and only used by, the tarball option above)"
                ),
                default="",
                required=False,
            )
        )
    return parameters


# Force build entry point for the dispatcher. Must be loaded on whichever
# master serves the www UI, since ForceScheduler availability is resolved
# per-process (master.allSchedulers()), not shared via the DB.
FOUNDRY_FORCE_SCHEDULERS = []
FOUNDRY_FORCE_SCHEDULERS.append(
    schedulers.ForceScheduler(
        name="foundry_force_scheduler",
        builderNames=[foundry_builders.DISPATCHER_BUILDER.name],
        # No plugin picker: the dispatcher clones Foundry and discovers what
        # to build, so a plugin added there needs no change here.
        properties=_server_source_parameters(),
        codebases=[
            util.CodebaseParameter(
                codebase="",
                branch=util.FixedParameter(name="branch", default="main"),
                revision=util.FixedParameter(name="revision", default=""),
                repository=util.FixedParameter(
                    name="repository", default=FOUNDRY_REPO_URL
                ),
                project=util.FixedParameter(name="project", default="MariaDB/foundry"),
            )
        ],
    )
)

# Pull requests against Foundry itself, and nothing else: category "pull" is
# what buildbot's GitHub hook (www/hooks/github.py) stamps on pull request
# events, so push events on the same repository don't match. The dispatcher
# takes it from there -- it builds only the plugins the PR touches, always
# against the MariaDB Server mirrors, and saves no packages.
#
# Lives with the force scheduler rather than next to the Triggerables: this
# is an entry point, and it belongs on the master that receives the webhook.
FOUNDRY_CHANGE_SCHEDULERS = [
    schedulers.AnyBranchScheduler(
        name="foundry_pull_request_scheduler",
        builderNames=[foundry_builders.DISPATCHER_BUILDER.name],
        treeStableTimer=60,
        change_filter=util.ChangeFilter(
            repository=FOUNDRY_REPO_URL,
            category="pull",
        ),
    )
]

# One Triggerable per supported MariaDB version, holding the builders that
# version runs -- see FOUNDRY_TRIGGERABLE_BUILDERS in
# configuration/builders/definitions/foundry/builders.py. The dispatcher
# builder (foundry-trigger-builders) fires one per version, setting
# mariadb_version, foundry_plugins and (on the CI side) tarbuildnum, via
# getSchedulersAndProperties in configuration/steps/commands/trigger.py.
# Must be loaded on whichever master executes the dispatcher build (i.e. the
# master owning its workers), since Trigger steps look schedulers up on
# their own process (master.scheduler_manager.namedServices).
FOUNDRY_TRIGGERABLE_SCHEDULERS = [
    schedulers.Triggerable(name=scheduler_name, builderNames=builder_names)
    for scheduler_name, builder_names in foundry_builders.FOUNDRY_TRIGGERABLE_BUILDERS.items()
]
