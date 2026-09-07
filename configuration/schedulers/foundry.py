import configuration.builders.definitions.foundry.builders as foundry_builders
from buildbot.plugins import schedulers, util

# Force build entry point for the dispatcher. Must be loaded on whichever
# master serves the www UI, since ForceScheduler availability is resolved
# per-process (master.allSchedulers()), not shared via the DB.
FOUNDRY_FORCE_SCHEDULERS = []
FOUNDRY_FORCE_SCHEDULERS.append(
    schedulers.ForceScheduler(
        name="foundry_force_scheduler",
        builderNames=[foundry_builders.DISPATCHER_BUILDER.name],
        properties=[
            util.ChoiceStringParameter(
                name="plugin",
                label="Plugin to build",
                choices=foundry_builders.FOUNDRY_PLUGINS,
                default=foundry_builders.FOUNDRY_PLUGINS[0],
            ),
        ],
        codebases=[
            util.CodebaseParameter(
                codebase="",
                branch=util.FixedParameter(name="branch", default="main"),
                revision=util.FixedParameter(name="revision", default=""),
                repository=util.FixedParameter(name="repository", default="https://github.com/MariaDB/foundry"),
                project=util.FixedParameter(name="project", default="MariaDB/foundry"),
            )
        ]
    )
)

# One Triggerable per supported MariaDB version, holding whichever packages
# that version builds -- see FOUNDRY_MARIADB_VERSIONS in
# configuration/builders/definitions/foundry/foundry.yaml. The dispatcher
# builder (foundry-trigger-builders) fires each of these once, setting
# mariadb_version, via getSchedulersAndProperties in
# configuration/steps/commands/trigger.py.
# Must be loaded on whichever master executes the dispatcher build (i.e. the
# master owning its workers), since Trigger steps look schedulers up on
# their own process (master.scheduler_manager.namedServices).
FOUNDRY_TRIGGERABLE_SCHEDULERS = [
    schedulers.Triggerable(
        name=foundry_builders.foundry_scheduler_name(version),
        builderNames=[
            builder.name
            for package in version_config["packages"]
            for builder in foundry_builders.FOUNDRY_BUILDERS_BY_PACKAGE[package]
        ],
    )
    for version, version_config in foundry_builders.FOUNDRY_MARIADB_VERSIONS.items()
]
