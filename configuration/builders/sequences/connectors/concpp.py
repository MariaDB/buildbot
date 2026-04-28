import os
from pathlib import PurePath

import configuration.steps.commands.trigger as trigger
from configuration.builders.infra.runtime import (
    BuildSequence,
    DockerConfig,
    InContainer,
)
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL, BashCommand, PowerShellCommand
from configuration.steps.commands.compile import MAKE, CompileCMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchTarball, GitInitFromCommit
from configuration.steps.commands.packages import (
    ArchiveSource,
    InstallDEBPackages,
    InstallRPMPackages,
    SavePackages,
    SetupDEBRepo,
    SetupRPMRepo,
)
from configuration.steps.commands.srpm import (
    SRPMCompare,
    SRPMInstallBuildDeps,
    SRPMRebuild,
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
                            CMakeOption(WITH.OPENSSL, False),
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

    # Both C/C++ 1.0 and 1.1 use C/C 3.3
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=BashCommand(
                    name="cpp_to_mariadb_repo",
                    cmd="""
    file=$(echo mariadb-connector-cpp-*-src.tar.gz)
    version=${file#*-cpp-}
    version=${version%%-src.tar.gz}
    cpp_version=$(echo "$version" | cut -d. -f1,2)

    if [[ $cpp_version == 1.0 ]] || [[ $cpp_version == 1.1 ]]; then
        echo 10.11
    else
        echo 11.8
    fi
    """,
                ),
                property="cpp_to_mariadb_repo",
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=BashCommand(
                    name="cpp_version",
                    cmd="""
    file=$(echo mariadb-connector-cpp-*-src.tar.gz)
    version=${file#*-cpp-}
    version=${version%%-src.tar.gz}
    cpp_version=$(echo "$version" | cut -d. -f1,2)
    echo "$cpp_version"
    """,
                ),
                property="cpp_version",
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
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-cpp/%(prop:buildnumber)s",
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

    sequence.add_step(trigger.ConCPP())

    return sequence


def deb(
    config: DockerConfig,
    jobs: int,
    package_platform_suffix: str,
    source_path: str,
    deb_path: str,
    do_step_if=lambda props: True,
):
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupDEBRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/repo/%(prop:cpp_to_mariadb_repo)s",
                ),
                options=StepOptions(
                    description="DEB - Setup MariaDB repository",
                    descriptionDone="DEB - MariaDB repository setup done",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    # During the deb packaging steps, we need to have recent development files of
    # the MariaDB client library available in the container,
    # as the C/C++ build needs to link to the system level library, hence installing from
    # the MariaDB repository instead of using the older version from Debian repos
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallDEBPackages(
                    packages=["libmariadb-dev"],
                ),
                options=StepOptions(
                    description="DEB - Install MariaDB development packages",
                    descriptionDone="DEB - MariaDB development packages installed",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="DEB",
                    cmake_generator=CMakeGenerator(
                        source_path=source_path,
                        builddir=deb_path,
                        use_ccache=True,
                        flags=[
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
                            CMakeOption(
                                OTHER.PACKAGE_PLATFORM_SUFFIX, package_platform_suffix
                            ),
                            CMakeOption(OTHER.DEB, True),
                            CMakeOption(OTHER.CPACK_GENERATOR, "DEB"),
                            CMakeOption(OTHER.MARIADB_LINK_DYNAMIC, True),
                            CMakeOption(OTHER.USE_SYSTEM_INSTALLED_LIB, True),
                        ],
                    ),
                ),
                options=StepOptions(
                    description="DEB - Configure CMake",
                    descriptionDone="DEB - CMake configured",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=CompileCMakeCommand(
                    workdir=PurePath(deb_path),
                    target=MAKE.PACKAGE,
                    jobs=jobs,
                ),
                options=StepOptions(
                    description="DEB - Build package",
                    descriptionDone="DEB - Package built",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
        ),
    )

    return sequence


def rpm(
    config: DockerConfig,
    jobs: int,
    package_platform_suffix: str,
    source_path: str,
    rpm_path: str,
    os_name: str,
):
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupRPMRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/yum/%(prop:cpp_to_mariadb_repo)s",
                    name=f"{os_name}:Setup MariaDB repository",
                ),
                options=StepOptions(
                    description=f"{os_name}:Setup MariaDB repository",
                    descriptionDone=f"{os_name}:MariaDB repository setup done",
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    # the same motivation as in the deb sequence, we need the recent
    # development files of the MariaDB client library, hence installing MariaDB-devel
    # from the MariaDB repository
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallRPMPackages(
                    packages=["MariaDB-devel"],
                ),
                options=StepOptions(
                    description=f"{os_name}:Install MariaDB development packages",
                    descriptionDone=f"{os_name}:MariaDB development packages installed",
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="RPM",
                    cmake_generator=CMakeGenerator(
                        source_path=source_path,
                        builddir=rpm_path,
                        use_ccache=True,
                        flags=[
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
                            CMakeOption(
                                OTHER.PACKAGE_PLATFORM_SUFFIX, package_platform_suffix
                            ),
                            CMakeOption(OTHER.RPM, True),
                            CMakeOption(OTHER.CPACK_GENERATOR, "RPM"),
                            CMakeOption(OTHER.MARIADB_LINK_DYNAMIC, True),
                            CMakeOption(OTHER.USE_SYSTEM_INSTALLED_LIB, True),
                        ],
                    ),
                ),
                options=StepOptions(
                    description="RPM - Configure CMake",
                    descriptionDone="RPM - CMake configured",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=CompileCMakeCommand(
                    workdir=PurePath(rpm_path),
                    target=MAKE.PACKAGE_SOURCE,
                    jobs=jobs,
                ),
                options=StepOptions(
                    description="RPM - Build source package",
                    descriptionDone="RPM - Source package built",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=CompileCMakeCommand(
                    workdir=PurePath(rpm_path),
                    target=MAKE.PACKAGE,
                    jobs=jobs,
                ),
                options=StepOptions(
                    description="RPM - Build package",
                    descriptionDone="RPM - Package built",
                ),
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=BashCommand(
                    name="Move RPM packages",
                    workdir=PurePath(rpm_path),
                    cmd=f"mkdir -p srpms rpms && mv ./*.src.rpm srpms/ && cp ./*.rpm rpms/",
                ),
                options=StepOptions(
                    description="RPM - Move packages",
                    descriptionDone="RPM - Packages moved",
                ),
            ),
            docker_environment=config,
        ),
    )

    return sequence


def deb_pkg_tests(config: DockerConfig, deb_path: str, do_step_if=lambda props: True):
    """
    This sequence should take a clean Docker environment as an input to ensure
    that all dependencies required by the .deb are correctly specified,
    and then run the C/C++ tests.
    """
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupDEBRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/repo/%(prop:cpp_to_mariadb_repo)s",
                ),
                options=StepOptions(
                    description="DEB - Setup MariaDB repository",
                    descriptionDone="DEB - MariaDB repository setup done",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    # Testing that .deb can be installed and all dependencies are correctly specified,
    # by installing in a clean environment and running the C/C++ tests
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallDEBPackages(
                    packages=["./*.deb"],
                    workdir=PurePath(deb_path),
                ),
                options=StepOptions(
                    description="DEB - Install .deb packages",
                    descriptionDone="DEB - .deb packages installed",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=BashCommand(
                    name="Test DEB - C/C++ Tests",
                    workdir=PurePath(f"{deb_path}/test"),
                    cmd="export TEST_HOST=$SIDECAR_HOST && ./cjportedtests",
                    user="root",
                ),
                env_vars=[
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                ],
                options=StepOptions(
                    description="DEB - Run C/C++ tests",
                    descriptionDone="DEB - C/C++ tests done",
                    doStepIf=do_step_if,
                ),
            ),
            docker_environment=config,
        ),
    )
    return sequence


def rpm_pkg_tests(config: DockerConfig, rpm_path: str, os_name: str):
    """
    This sequence should take a clean Docker environment as an input to ensure
    that all dependencies required by the .rpm are correctly specified,
    and then run the C/C++ tests.
    """
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupRPMRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/yum/%(prop:cpp_to_mariadb_repo)s",
                    name=f"{os_name}:Setup MariaDB repository",
                ),
                options=StepOptions(
                    description=f"{os_name}:Setup MariaDB repository",
                    descriptionDone=f"{os_name}:MariaDB repository setup done",
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    # Testing that .rpm can be installed and all dependencies are correctly
    # specified, by installing in a clean environment and running the C/C++ tests
    sequence.add_step(
        InContainer(
            ShellStep(
                command=InstallRPMPackages(
                    packages=["./*.rpm"],
                    workdir=PurePath(rpm_path),
                    name=f"{os_name}:Install .rpm pkg",
                ),
                options=StepOptions(
                    description=f"{os_name}:Install .rpm packages",
                    descriptionDone=f"{os_name}:.rpm packages installed",
                ),
            ),
            docker_environment=config,
            container_commit=True,
        ),
    )

    sequence.add_step(
        InContainer(
            ShellStep(
                command=BashCommand(
                    name=f"{os_name}:Test C/C++ Tests",
                    workdir=PurePath(f"{rpm_path}/test"),
                    cmd="export TEST_HOST=$SIDECAR_HOST && ./cjportedtests",
                    user="root",
                ),
                env_vars=[
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                ],
                options=StepOptions(
                    description=f"{os_name}:Run C/C++ tests",
                    descriptionDone=f"{os_name}:C/C++ tests done",
                ),
            ),
            docker_environment=config,
        ),
    )
    return sequence


def srpm_pkg_test(config: DockerConfig, jobs, rpms_dir: str):
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=SRPMInstallBuildDeps(
                    workdir=PurePath(rpms_dir),
                ),
                options=StepOptions(
                    description="SRPM - Installing build dependencies",
                    descriptionDone="SRPM - Build dependencies installed",
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SRPMRebuild(
                    jobs=jobs,
                    workdir=PurePath(rpms_dir),
                ),
                options=StepOptions(
                    description="SRPM - Rebuild",
                    descriptionDone="SRPM - Rebuild done",
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SRPMCompare(
                    workdir=PurePath(rpms_dir),
                    ci_rpms_dir="rpms",
                    rebuilt_rpms_dir="../../rpmbuild/RPMS",
                ),
                options=StepOptions(
                    description="SRPM - Compare",
                    descriptionDone="SRPM - Compare done",
                ),
                warn_on_fail=True,
            ),
        )
    )

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
        CMakeOption(OTHER.CONC_WITH_UNIT_TESTS, False),
        CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
        CMakeOption(OTHER.PACKAGE_PLATFORM_SUFFIX, package_platform_suffix),
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
        sequence.add_step(
            InContainer(
                ShellStep(
                    command=BashCommand(
                        name="Checkout latest C/C",
                        cmd="git fetch origin $(([ '%(prop:cpp_version)s' = '1.0' ] || [ '%(prop:cpp_version)s' = '1.1' ]) && echo 3.3 || echo 3.4) && git reset --hard FETCH_HEAD",
                        workdir=PurePath(source_path) / "libmariadb",
                    ),
                    options=StepOptions(
                        description="Checking out latest C/C",
                        descriptionDone="Checked out latest C/C",
                    ),
                ),
                docker_environment=config,
            )
        )
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

    # For the bintar test, we use libmariadb previously built from the source tree
    sequence.add_step(
        InContainer(
            ShellStep(
                command=BashCommand(
                    name="Test bintar - C/C++ ctest",
                    workdir=PurePath(f"{bintar_path}/test"),
                    cmd="export TEST_HOST=$SIDECAR_HOST && ctest --output-on-failure",
                ),
                env_vars=[
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                ]
                + (env_vars if env_vars else []),
                options=StepOptions(
                    description="Bintar - Run C/C++ ctest",
                    descriptionDone="Bintar - C/C++ ctest done",
                ),
            ),
            docker_environment=config,
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
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-cpp/%(prop:tarbuildnum)s/%(prop:buildername)s",
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
            CMakeOption(WITH.SSL, "SCHANNEL"),
            CMakeOption(OTHER.CONC_WITH_UNIT_TESTS, False),
            CMakeOption(OTHER.CONC_WITH_MSI, False),
            CMakeOption(OTHER.INSTALL_PLUGINDIR, "plugin"),
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
                name="C/C++ ctest",
                cmd="cd test && ctest --output-on-failure",
            ),
            env_vars=[
                ("TEST_UID", "root"),
                ("TEST_PASSWORD", "test"),
                ("TEST_PORT", "3306"),
                ("TEST_SCHEMA", "test"),
            ],
            options=StepOptions(
                description="Run C/C++ ctest",
                descriptionDone="C/C++ ctest done",
            ),
        ),
    )

    sequence.add_step(
        PropFromShellStep(
            command=BashCommand(
                name="find MSI",
                cmd="find . -maxdepth 1 -type f -name '*.msi' -exec basename {} \\;",
                workdir=PurePath("wininstall"),
            ),
            property="packages",
        ),
    )

    sequence.add_step(
        FileUpload(
            workersrc="wininstall\\%(prop:packages)s",
            masterdest="/srv/buildbot/connectors/cpp/%(prop:tarbuildnum)s/%(prop:buildername)s/%(prop:packages)s",
            mode=0o755,
            url=f"{os.environ['ARTIFACTS_URL']}/connector-cpp/%(prop:tarbuildnum)s/%(prop:buildername)s/",
        )
    )
    return sequence
