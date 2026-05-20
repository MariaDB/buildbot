import os
from pathlib import PurePath

import configuration.steps.commands.trigger as trigger
from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL, BashCommand
from configuration.steps.commands.compile import MAKE, CompileCMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchTarball, GitInitFromCommit
from configuration.steps.commands.packages import (
    ArchiveSource,
    InstallRPMPackages,
    SavePackages,
)
from configuration.steps.commands.upload import FileUpload
from configuration.steps.commands.util import PrintEnvironmentDetails
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    BUILDPLATFORM,
    BUILDTOOLS,
    CMAKE,
    OTHER,
    WITH,
    BuildType,
    CMakeOption,
)
from configuration.steps.remote import PropFromShellStep, ShellStep


def git_clone_step(step_wrapping_fn=lambda step: step, source_path: str = "."):
    source_path = PurePath(source_path)
    return step_wrapping_fn(
        ShellStep(
            command=GitInitFromCommit(
                repo_url="%(prop:repository)s",
                commit="%(prop:revision)s",
                workdir=source_path,
            ),
            options=StepOptions(
                description="Initialize git repository",
                descriptionDone="Git repository initialized",
            ),
        ),
    )


def git_clone_sq(config: DockerConfig = None, source_path: str = "."):
    sequence = BuildSequence()
    if config:
        sequence.add_step(
            git_clone_step(
                lambda step: InContainer(
                    step,
                    docker_environment=config,
                ),
                source_path=source_path,
            )
        )
        return sequence
    sequence.add_step(git_clone_step(source_path=source_path))
    return sequence


def tarball(config: DockerConfig):
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))
    sequence.add_step(
        git_clone_step(lambda step: InContainer(step, docker_environment=config))
    )
    sequence.add_step(
        InContainer(
            ShellStep(
                command=ArchiveSource(
                    input_dir=PurePath("."),
                    output_dir=PurePath("ci_source"),
                    tarball_name="ci.tar.gz",
                    generate_sha256=True,
                ),
                options=StepOptions(
                    description="Archive source code",
                    descriptionDone="Source code archived",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="Create source package",
                    cmake_generator=CMakeGenerator(
                        use_ccache=False,
                        flags=[
                            CMakeOption(OTHER.GIT_BUILD_SRCPKG, True),
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
                        ],
                    ),
                ),
                options=StepOptions(
                    description="Create source package - Configure CMake",
                    descriptionDone="Create source package - CMake configured",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SavePackages(
                    packages=[
                        "ci_source/ci.tar.gz",
                        "*src.tar.gz",
                        "ci_source/sha256sums.txt",
                    ],
                    destination="/packages/%(prop:buildnumber)s",
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-c/%(prop:buildnumber)s",
                    url_text="Source tarball",
                ),
                options=StepOptions(
                    description="Save source packages",
                    descriptionDone="Source packages saved",
                ),
            ),
            docker_environment=config,
        )
    )

    sequence.add_step(trigger.ConC())

    return sequence


def get_source_package(config: DockerConfig, source_path: str):
    sequence = BuildSequence()
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=FetchTarball(workdir=PurePath(source_path)),
                options=StepOptions(
                    description="Fetch tarball",
                    descriptionDone="Fetch tarball done",
                ),
            ),
            docker_environment=config,
        )
    )
    return sequence


def bintar(
    config: DockerConfig,
    test_environments: list[DockerConfig],
    jobs: int,
    package_platform_suffix: str,
    bintar_path: str,
    source_path: str,
    with_asan_ubsan=False,
    with_msan=False,
):
    sequence = BuildSequence()
    env_vars = None
    flags = [
        CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
        CMakeOption(OTHER.PACKAGE_PLATFORM_SUFFIX, package_platform_suffix),
        CMakeOption(WITH.DOCS, True),
    ]

    if with_msan:
        flags.append(CMakeOption(WITH.MSAN, True))
        flags.append(
            CMakeOption(
                CMAKE.EXE_LINKER_FLAGS, "-L${MSAN_LIBDIR} -Wl,-rpath,${MSAN_LIBDIR}"
            )
        )
        flags.append(
            CMakeOption(
                CMAKE.SHARED_LINKER_FLAGS, "-L${MSAN_LIBDIR} -Wl,-rpath,${MSAN_LIBDIR}"
            )
        )
        flags.append(
            CMakeOption(
                CMAKE.MODULE_LINKER_FLAGS, "-L${MSAN_LIBDIR} -Wl,-rpath,${MSAN_LIBDIR}"
            )
        )

    if with_asan_ubsan:
        flags.append(CMakeOption(WITH.ASAN, True))
        flags.append(CMakeOption(WITH.UBSAN, True))
        env_vars = [
            (
                "ASAN_OPTIONS",
                "detect_stack_use_after_return=1:detect_leaks=1:abort_on_error=1:atexit=0:detect_invalid_pointer_pairs=3:dump_instruction_bytes=1:allocator_may_return_null=1",
            ),
            (
                "UBSAN_OPTIONS",
                f"suppressions=/home/buildbot/{source_path}/UBSAN.supp:print_stacktrace=1:report_error_type=1:halt_on_error=1",
            ),
        ]

    sequence.add_step(
        InContainer(
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="Bintar",
                    cmake_generator=CMakeGenerator(
                        source_path=source_path,
                        builddir=bintar_path,
                        use_ccache=True,
                        flags=flags,
                    ),
                ),
                env_vars=env_vars,
                options=StepOptions(
                    description="Bintar - Configure CMake",
                    descriptionDone="Bintar - CMake configured",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=CompileCMakeCommand(
                    workdir=PurePath(bintar_path),
                    target=MAKE.PACKAGE,
                    jobs=jobs,
                ),
                env_vars=env_vars,
                options=StepOptions(
                    description="Bintar - Compile",
                    descriptionDone="Bintar - Compile done",
                ),
            ),
            docker_environment=config,
        ),
    )

    for test_env in test_environments:
        if test_env:
            if "almalinux" in test_env.image_tag or "rockylinux" in test_env.image_tag:
                sequence.add_step(
                    InContainer(
                        ShellStep(
                            command=InstallRPMPackages(
                                packages=["epel-release"],
                                name="Install EPEL repository",
                            ),
                        ),
                        container_commit=True,
                        docker_environment=test_env,
                    )
                )

                sequence.add_step(
                    InContainer(
                        ShellStep(
                            command=InstallRPMPackages(
                                packages=["cmake", "python3-pyOpenSSL"],
                                name="Install packages for testing",
                            ),
                        ),
                        container_commit=True,
                        docker_environment=test_env,
                    )
                )

            sequence.add_step(
                InContainer(
                    ShellStep(
                        command=BashCommand(
                            name="Test bintar on {}".format(test_env.image_tag),
                            workdir=PurePath(f"{bintar_path}/unittest/libmariadb"),
                            cmd="export MYSQL_TEST_HOST=$SIDECAR_HOST && ctest --output-on-failure",
                            user="root",
                        ),
                        env_vars=[
                            ("MYSQL_TEST_USER", "root"),
                            ("MYSQL_TEST_PASSWD", "test"),
                            ("MYSQL_TEST_PORT", "3306"),
                            ("MYSQL_TEST_DB", "test"),
                            ("MYSQL_TEST_VERBOSE", "true"),
                            ("MARIADB_CC_TEST", 1),
                            ("MYSQL_TEST_TLS", 0),
                            ("MYSQL_TEST_SSL_PORT", 0),
                        ]
                        + (env_vars if env_vars else []),
                        options=StepOptions(
                            description="Bintar - Run C/C ctest",
                            descriptionDone="Bintar - C/C ctest done",
                        ),
                    ),
                    docker_environment=test_env,
                ),
            )
    return sequence


def save_packages(config: DockerConfig, packages: list[str], user: str = "buildbot"):
    sequence = BuildSequence()
    sequence.add_step(
        InContainer(
            ShellStep(
                command=SavePackages(
                    packages=packages,
                    destination="/packages/%(prop:tarbuildnum)s/%(prop:buildername)s",
                    user=user,
                ),
                options=StepOptions(
                    description="Save packages",
                    descriptionDone="Save packages done",
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-c/%(prop:tarbuildnum)s/%(prop:buildername)s",
                    url_text="Packages",
                ),
            ),
            docker_environment=config,
        )
    )
    return sequence


def windows(jobs: int, target_platform: str):
    sequence = BuildSequence()
    sequence.add_step(git_clone_step())

    if target_platform == "32-bit":
        cmake_generator = CMakeGenerator(
            build_platform=BUILDPLATFORM.WIN32,
            build_tool=BUILDTOOLS.WINVS2022,
            flags=[],
        )
    if target_platform == "64-bit":
        cmake_generator = CMakeGenerator(build_tool=BUILDTOOLS.WINVS2022, flags=[])

    cmake_generator.flags.extend(
        [
            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
            CMakeOption(WITH.CURL, True),
            CMakeOption(WITH.MSI, True),
        ],
    )

    sequence.add_step(
        ShellStep(
            command=ConfigureMariaDBCMake(
                name="RelWithDebugInfo",
                cmake_generator=cmake_generator,
            ),
            options=StepOptions(
                description="Configure CMake",
                descriptionDone="CMake configured",
            ),
        ),
    )

    sequence.add_step(
        ShellStep(
            command=CompileCMakeCommand(
                jobs=jobs,
                config=BuildType.RELWITHDEBUG,
            ),
            options=StepOptions(
                description="Build package",
                descriptionDone="Package built",
            ),
        ),
    )

    sequence.add_step(
        ShellStep(
            command=BashCommand(
                name="C/C ctest",
                cmd="cd unittest/libmariadb && ctest --output-on-failure",
            ),
            env_vars=[
                ("MYSQL_TEST_USER", "root"),
                ("MYSQL_TEST_PASSWD", "test"),
                ("MYSQL_TEST_PORT", "3306"),
                ("MYSQL_TEST_DB", "test"),
                ("MYSQL_TEST_HOST", "127.0.0.1"),
                ("MARIADB_CC_TEST", "1"),
                ("MYSQL_TEST_TLS", "0"),
            ],
            options=StepOptions(
                description="Run C/C ctest",
                descriptionDone="C/C ctest done",
            ),
        ),
    )

    sequence.add_step(
        PropFromShellStep(
            command=BashCommand(
                name="find MSI",
                cmd="find . -maxdepth 4 -type f -name '*.msi' -exec basename {} \\;",
                workdir=PurePath("wininstall"),
            ),
            property="packages",
        ),
    )

    # sequence.add_step(
    #     FileUpload(
    #         workersrc="wininstall\\%(prop:packages)s",
    #         masterdest="/srv/buildbot/connectors/c/%(prop:tarbuildnum)s/%(prop:buildername)s/%(prop:packages)s",
    #         mode=0o755,
    #         url=f"{os.environ['ARTIFACTS_URL']}/connector-c/%(prop:tarbuildnum)s/%(prop:buildername)s/",
    #     )
    # )
    return sequence
