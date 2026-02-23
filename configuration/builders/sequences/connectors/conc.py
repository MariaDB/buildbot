import configuration.steps.commands.trigger as trigger
from configuration.builders.infra.runtime import BuildSequence
from configuration.steps.commands.util import PrintEnvironmentDetails
from configuration.steps.remote import ShellStep


def tarball():
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))
    sequence.add_step(trigger.ConC())

    return sequence


def deb():
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    return sequence


def rpm():
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    return sequence
