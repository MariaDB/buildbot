import os

from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL
from configuration.steps.commands.packages import SavePackages
from configuration.steps.commands.util import InferScript, PrintEnvironmentDetails
from configuration.steps.remote import ShellStep


def infer(config: DockerConfig):
    sequence = BuildSequence()

    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=InferScript(),
                options=StepOptions(
                    description="running infer analysis",
                    descriptionDone="infer analysis complete",
                ),
                env_vars=[("JOBS", str("%(prop:jobs)s"))],
                timeout=7200,
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SavePackages(
                    packages=["infer_results"],
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                    url_text="Infer artifacts/logs",
                ),
                options=StepOptions(
                    alwaysRun=True,
                    description="saving infer analysis results",
                    descriptionDone="infer analysis results saved",
                ),
            ),
        )
    )
    return sequence
