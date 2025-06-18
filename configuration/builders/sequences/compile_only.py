from pathlib import PurePath

from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.commands.compile import MAKE, CompileMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import GitInitFromCommit
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    CMAKE,
    OTHER,
    PLUGIN,
    WITH,
    WITHOUT,
    BuildType,
    CMakeOption,
)
from configuration.steps.remote import ShellStep


def nopart_debug(
    config,
    jobs,
):
    ### INIT
    sequence = BuildSequence()

    for step in steps_compile_only(
        config,
        jobs,
        cmake_step_name="Debug - No Partition",
        cmake_flags=[
            CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG),
            CMakeOption(PLUGIN.PARTITION, False),
        ],
    ):
        sequence.add_step(step)

    return sequence


def minimal(
    config,
    jobs,
):
    ### INIT
    sequence = BuildSequence()

    for step in steps_compile_only(
        config,
        jobs,
        cmake_step_name="Minimal",
        cmake_flags=[
            CMakeOption(WITH.NONE, True),
            CMakeOption(WITH.WSREP, False),
            CMakeOption(PLUGIN.PARTITION, False),
            CMakeOption(PLUGIN.PERFSCHEMA_FEATURE, False),
            CMakeOption(PLUGIN.FEEDBACK, False),
            CMakeOption(PLUGIN.INNOBASE, False),
            CMakeOption(PLUGIN.SEQUENCE, False),
            CMakeOption(PLUGIN.USER_VARIABLES, False),
            CMakeOption(PLUGIN.THREAD_POOL_INFO, False),
        ],
    ):
        sequence.add_step(step)

    return sequence


def no_perf_schema(
    config,
    jobs,
):
    ### INIT
    sequence = BuildSequence()

    for step in steps_compile_only(
        config,
        jobs,
        cmake_step_name="No Perf Schema",
        cmake_flags=[
            CMakeOption(CMAKE.INSTALL_PREFIX, PurePath("/usr/local/mysql")),
            CMakeOption(PLUGIN.PERFSCHEMA_FEATURE, False),
            CMakeOption(WITH.EXTRA_CHARSETS, "complex"),
            CMakeOption(WITH.SSL, "system"),
            CMakeOption(OTHER.ENABLED_PROFILING, "OFF"),
        ],
    ):
        sequence.add_step(step)

    return sequence


def without_server(
    config,
    jobs,
):
    ### INIT
    sequence = BuildSequence()

    for step in steps_compile_only(
        config,
        jobs,
        cmake_step_name="Without Server",
        cmake_flags=[
            CMakeOption(WITHOUT.SERVER, True),
        ],
    ):
        sequence.add_step(step)

    return sequence


def steps_compile_only(
    config: DockerConfig,
    jobs: int,
    cmake_flags: list[CMakeOption],
    cmake_step_name: str,
):
    ### INIT
    steps = []

    steps.extend(
        [
            InContainer(
                ShellStep(
                    command=GitInitFromCommit(
                        repo_url="%(prop:repository)s",
                        commit="%(prop:revision)s",
                    ),
                ),
                docker_environment=config,
            ),
            InContainer(
                ShellStep(
                    command=ConfigureMariaDBCMake(
                        name=cmake_step_name,
                        cmake_generator=CMakeGenerator(
                            use_ccache=True,
                            flags=cmake_flags,
                        ),
                    ),
                ),
                docker_environment=config,
            ),
            InContainer(
                ShellStep(
                    command=CompileMakeCommand(
                        option=MAKE.COMPILE,
                        jobs=jobs,
                        output_sync=True,
                        verbose=True,
                    )
                ),
                docker_environment=config,
            ),
        ]
    )

    return steps
