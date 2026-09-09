from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.builders.sequences.foundry.autobake import clone_foundry_step
from configuration.steps.commands import trigger
from configuration.steps.commands.foundry import (
    BASE_BRANCH_ENV,
    BRANCH_ENV,
    DiscoverFoundryPlugins,
)
from configuration.steps.remote import PropFromShellStep

# What the discovery step needs to know about the run it was started by.
# "basename" is the pull request's target branch, set on the change by
# buildbot's GitHub hook (www/hooks/github.py) and carried onto the build;
# it is absent on a force build, where the discovery step doesn't need it.
_EVENT_ENV = [
    (BRANCH_ENV, "%(prop:branch)s"),
    (BASE_BRANCH_ENV, "%(prop:basename:-)s"),
]


def trigger_foundry(config: DockerConfig, trigger_specs):
    # The dispatcher clones Foundry only to find out what to build: which
    # plugins exist (or, for a pull request, which ones it touches). The
    # package builders clone it again for themselves -- this checkout never
    # builds anything.
    #
    # trigger_specs: list of per-MariaDB-version dicts -- see
    # configuration/builders/definitions/foundry/builders.py.
    sequence = BuildSequence()
    sequence.add_step(clone_foundry_step(config, depth=0))
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=DiscoverFoundryPlugins(),
                property="foundry_plugins",
                env_vars=_EVENT_ENV,
            ),
            docker_environment=config,
        )
    )
    sequence.add_step(trigger.FoundryDispatch(trigger_specs))
    return sequence
