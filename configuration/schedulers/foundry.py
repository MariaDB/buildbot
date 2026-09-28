import configuration.builders.definitions.foundry.builders as foundry_builders
from buildbot.plugins import schedulers, util
from configuration.builders.definitions.foundry import sources
from configuration.schedulers.foundry_access import force_access

_REPOSITORY = foundry_builders.FOUNDRY_REPOSITORY


def _server_source_parameters():
    # Per MariaDB version: where its server packages come from, and the
    # tarbuildnum for sources.CI_TARBALL. A version not on the mirrors yet
    # can only use a CI tarball, and is skipped by default.
    parameters = []
    for version, version_config in foundry_builders.FOUNDRY_MARIADB_VERSIONS.items():
        mirrored = sources.on_mirrors(version_config)
        parameters.append(
            util.ChoiceStringParameter(
                name=sources.source_property(version),
                label=(
                    f"MariaDB {version}: server packages"
                    + ("" if mirrored else " (not on the mirrors yet)")
                ),
                choices=sources.choices(mirrored),
                default=sources.default(mirrored),
            )
        )
        parameters.append(
            util.StringParameter(
                name=sources.tarbuildnum_property(version),
                # No angle brackets or quotes: labels are rendered as HTML.
                label=(
                    f"MariaDB {version}: ci.mariadb.org tarbuildnum "
                    "(required by, and only used by, the tarball option above)"
                ),
                default="",
                required=False,
            )
        )
    return parameters


# Loaded on the master serving the UI: force schedulers are per process.
FOUNDRY_FORCE_SCHEDULERS = [
    schedulers.ForceScheduler(
        name="foundry_force_scheduler",
        builderNames=[foundry_builders.DISPATCHER_BUILDER.name],
        properties=[
            # Full SHA only: GitHub doesn't fetch by abbreviated hash.
            util.StringParameter(
                name="foundry_commit",
                label=(
                    "Foundry commit (full SHA, empty for the tip of "
                    f"{_REPOSITORY['branch']})"
                ),
                default="",
                regex=r"^([0-9a-f]{40})?$",
            )
        ]
        + _server_source_parameters(),
        codebases=[
            util.CodebaseParameter(
                codebase="",
                branch=util.FixedParameter(
                    name="branch", default=_REPOSITORY["branch"]
                ),
                revision=util.FixedParameter(name="revision", default=""),
                repository=util.FixedParameter(
                    name="repository", default=_REPOSITORY["url"]
                ),
                project=util.FixedParameter(
                    name="project", default=_REPOSITORY["project"]
                ),
            )
        ],
    )
]

# Only force_users may force the dispatcher; see foundry_access.py.
FOUNDRY_ROLE_MATCHERS, FOUNDRY_AUTHZ_RULES = force_access(
    foundry_builders.DISPATCHER_BUILDER.name, foundry_builders.FOUNDRY_FORCE_USERS
)

# Pull requests on Foundry: the GitHub hook sets category "pull" on those,
# not on pushes. Loaded on the master receiving the webhook.
FOUNDRY_CHANGE_SCHEDULERS = [
    schedulers.AnyBranchScheduler(
        name="foundry_pull_request_scheduler",
        builderNames=[foundry_builders.DISPATCHER_BUILDER.name],
        treeStableTimer=60,
        change_filter=util.ChangeFilter(
            repository=_REPOSITORY["url"],
            category="pull",
        ),
    )
]

# The dispatcher's Triggerables, one or two per MariaDB version. Loaded on
# the master running the dispatcher: Trigger looks schedulers up in-process.
FOUNDRY_TRIGGERABLE_SCHEDULERS = [
    schedulers.Triggerable(name=scheduler_name, builderNames=builder_names)
    for scheduler_name, builder_names in foundry_builders.FOUNDRY_TRIGGERABLE_BUILDERS.items()
]
