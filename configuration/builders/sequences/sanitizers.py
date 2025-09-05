from pathlib import PurePath

from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.builders.sequences.helpers import (
    get_mtr_normal_steps,
    get_mtr_s3_steps,
    get_mtr_spider_steps,
    mtr_junit_reporter,
    save_mtr_logs,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.compile import CompileCMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchGitHub, FetchTarball
from configuration.steps.commands.util import PrintEnvironmentDetails
from configuration.steps.generators.cmake.compilers import ClangCompiler
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    CMAKE,
    PLUGIN,
    WITH,
    BuildType,
    CMakeOption,
)
from configuration.steps.generators.mtr.options import MTR, MTROption
from configuration.steps.remote import ShellStep


def asan_ubsan(
    config: DockerConfig,
    jobs: int,
    isDebugBuildType: bool,
):
    sequence = BuildSequence()

    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=False,
            step=ShellStep(
                command=FetchTarball(workdir=PurePath("src")),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        )
    )

    for asset in ["UBSAN.filter", "ASAN.filter"]:
        sequence.add_step(
            InContainer(
                docker_environment=config,
                container_commit=False,
                step=ShellStep(
                    command=FetchGitHub(
                        workdir=PurePath("bld"),
                        repo="mariadb-corporation/mariadb-qa",
                        asset=asset,
                        branch="master",
                    ),
                    options=StepOptions(descriptionDone=f"Fetch {asset}"),
                ),
            )
        )

    flags = [
        CMakeOption(WITH.ASAN, True),
        CMakeOption(WITH.ASAN_SCOPED, True),
        CMakeOption(WITH.UBSAN, True),
        CMakeOption(WITH.UNIT_TESTS, False),
        CMakeOption(PLUGIN.COLUMNSTORE_STORAGE_ENGINE, False),
    ]
    if isDebugBuildType:
        flags.append(CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG))
        flags.append(CMakeOption(WITH.DBUG_TRACE, False))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=ConfigureMariaDBCMake(
                    name="configure",
                    workdir=PurePath("bld"),
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=flags,
                        source_path="../src",
                        compiler=ClangCompiler(),
                    ),
                ),
                options=StepOptions(descriptionDone="Configure"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileCMakeCommand(
                    builddir="bld",
                    jobs=jobs,
                    verbose=True,
                ),
                options=StepOptions(descriptionDone="compile"),
            ),
        )
    )

    env_vars = [
        (
            "LSAN_OPTIONS",
            "print_suppressions=0,suppressions="
            + str(PurePath("/home", "buildbot", "src", "lsan.supp")),
        ),
        (
            "ASAN_OPTIONS",
            "suppressions="
            + str(PurePath("/home", "buildbot", "bld", "ASAN.filter"))
            + ":quarantine_size_mb=512:atexit=0:detect_invalid_pointer_pairs=3:dump_instruction_bytes=1:allocator_may_return_null=1",
        ),
        (
            "UBSAN_OPTIONS",
            "suppressions="
            + str(PurePath("/home", "buildbot", "bld", "UBSAN.filter"))
            + ":print_stacktrace=1:report_error_type=1",
        ),
        ("MTR_FEEDBACK_PLUGIN", "1"),
    ]

    ## ADD MTR TESTS
    for step in (
        get_mtr_normal_steps(
            jobs=jobs,
            env_vars=env_vars,
            halt_on_failure=False,
            path_to_test_runner=PurePath("bld", "mysql-test"),
            additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
        + get_mtr_s3_steps(
            jobs=jobs,
            env_vars=env_vars,
            halt_on_failure=False,
            additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
            path_to_test_runner=PurePath("bld", "mysql-test"),
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
        + get_mtr_spider_steps(
            jobs=jobs,
            env_vars=env_vars,
            halt_on_failure=False,
            additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
            path_to_test_runner=PurePath("bld", "mysql-test"),
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
        + [
            save_mtr_logs(
                step_wrapping_fn=lambda step: InContainer(
                    docker_environment=config, step=step
                ),
            ),
            mtr_junit_reporter(
                step_wrapping_fn=lambda step: InContainer(
                    docker_environment=config, step=step
                ),
            ),
        ]
    ):
        sequence.add_step(step)

    return sequence


def msan(
    config: DockerConfig,
    jobs: int,
    isDebugBuildType: bool,
):
    sequence = BuildSequence()

    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=False,
            step=ShellStep(
                command=FetchTarball(workdir=PurePath("src")),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        )
    )

    flags = [
        CMakeOption(WITH.MSAN, True),
        CMakeOption(
            CMAKE.EXE_LINKER_FLAGS, "-L${MSAN_LIBDIR} -Wl,-rpath=${MSAN_LIBDIR}"
        ),
        CMakeOption(
            CMAKE.MODULE_LINKER_FLAGS, "-L${MSAN_LIBDIR} -Wl,-rpath=${MSAN_LIBDIR}"
        ),
        CMakeOption(WITH.UNIT_TESTS, False),
        CMakeOption(WITH.ZLIB, "bundled"),
        CMakeOption(WITH.SYSTEMD, "no"),
        CMakeOption(PLUGIN.COLUMNSTORE_STORAGE_ENGINE, False),
        CMakeOption(PLUGIN.SPIDER_STORAGE_ENGINE, isDebugBuildType),
        CMakeOption(PLUGIN.ROCKSDB_STORAGE_ENGINE, False),
        CMakeOption(PLUGIN.OQGRAPH_STORAGE_ENGINE, False),
    ]
    if isDebugBuildType:
        flags.append(CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG))
        flags.append(CMakeOption(WITH.DBUG_TRACE, False))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=ConfigureMariaDBCMake(
                    name="configure",
                    workdir=PurePath("bld"),
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=flags,
                        source_path="../src",
                        compiler=ClangCompiler(),
                    ),
                ),
                options=StepOptions(descriptionDone="Configure"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileCMakeCommand(
                    builddir="bld",
                    jobs=jobs,
                    verbose=True,
                ),
                options=StepOptions(descriptionDone="compile"),
            ),
        )
    )

    env_vars = [
        (
            "MSAN_OPTIONS",
            "abort_on_error=1:poison_in_dtor=0",
        ),
        ("MTR_FEEDBACK_PLUGIN", "1"),
    ]

    ## ADD MTR TESTS
    steps = get_mtr_normal_steps(
        jobs=jobs,
        env_vars=env_vars,
        halt_on_failure=False,
        path_to_test_runner=PurePath("bld", "mysql-test"),
        additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
        step_wrapping_fn=lambda step: InContainer(docker_environment=config, step=step),
    ) + get_mtr_s3_steps(
        jobs=jobs,
        env_vars=env_vars,
        halt_on_failure=False,
        additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
        path_to_test_runner=PurePath("bld", "mysql-test"),
        step_wrapping_fn=lambda step: InContainer(docker_environment=config, step=step),
    )
    if isDebugBuildType:
        steps += get_mtr_spider_steps(
            jobs=jobs,
            env_vars=env_vars,
            halt_on_failure=False,
            additional_mtr_options=[MTROption(MTR.BIG_TEST, True)],
            path_to_test_runner=PurePath("bld", "mysql-test"),
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    steps += [
        save_mtr_logs(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ),
        mtr_junit_reporter(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ),
    ]

    for step in steps:
        sequence.add_step(step)

    return sequence
