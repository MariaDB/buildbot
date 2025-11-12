from pathlib import PurePath

from configuration.builders.infra.runtime import BuildSequence, InContainer
from configuration.builders.sequences.helpers import mtr_junit_reporter, save_mtr_logs
from configuration.steps.base import StepOptions
from configuration.steps.commands.compile import MAKE, CompileMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchTarball
from configuration.steps.commands.mtr import MTRTest
from configuration.steps.commands.util import PrintEnvironmentDetails
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    CMAKE,
    PLUGIN,
    BuildType,
    CMakeOption,
)
from configuration.steps.generators.mtr.generator import MTRGenerator
from configuration.steps.generators.mtr.options import MTR, MTROption
from configuration.steps.remote import ShellStep

MTR_PATH_TO_SAVE_LOGS = PurePath("/home/buildbot/mtr/logs")


def big_test(config, jobs):
    sequence = BuildSequence()
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))
    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=False,
            step=ShellStep(
                command=FetchTarball(),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        )
    )
    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=ConfigureMariaDBCMake(
                    name="Configure RELWITHDEBUG",
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=[
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
                            CMakeOption(PLUGIN.ROCKSDB_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.TOKUDB_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.MROONGA_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.OQGRAPH_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.SPIDER_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.SPHINX_STORAGE_ENGINE, False),
                        ],
                    ),
                ),
                options=StepOptions(
                    description="Running CMake Configure",
                    descriptionDone="CMake Configure Done",
                ),
            ),
        )
    )
    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileMakeCommand(
                    option=MAKE.COMPILE,
                    jobs=jobs,
                    verbose=True,
                    output_sync=True,
                ),
                options=StepOptions(
                    description="Running MAKE compile",
                    descriptionDone="MAKE compile done",
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                MTRTest(
                    name="nm big tests",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "nm",
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 2),
                            MTROption(MTR.MAX_SAVE_DATADIR, 10),
                            MTROption(MTR.MAX_TEST_FAIL, 20),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/nm"),
                            MTROption(MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "nm.xml"),
                            MTROption(MTR.BIG_TEST, True),
                            MTROption(MTR.SKIP_TEST, "archive.archive-big"),
                        ],
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=True,
                    description="Running MTR tests",
                    descriptionDone="MTR tests done",
                ),
            ),
        )
    )

    sequence.add_step(
        save_mtr_logs(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    )

    sequence.add_step(
        mtr_junit_reporter(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ),
    )

    return sequence
