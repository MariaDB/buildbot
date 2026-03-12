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
from configuration.steps.commands.util import PrintEnvironmentDetails
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    CMAKE,
    OTHER,
    WITH,
    BuildType,
    CMakeOption,
)
from configuration.steps.remote import PropFromShellStep, ShellStep


def tarball(config: DockerConfig):
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))
    sequence.add_step(
        InContainer(
            ShellStep(
                command=GitInitFromCommit(
                    repo_url="%(prop:repository)s",
                    commit="%(prop:revision)s",
                ),
                options=StepOptions(
                    description="Initialize git repository",
                    descriptionDone="Git repository initialized",
                ),
            ),
            docker_environment=config,
        ),
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

    # Connector/ODBC 3.1 will need C/C 3.3 from MariaDB repos which is present in server 10.11 branch
    # Connector/ODBC 3.2 will need C/C 3.4 which is present in server versions >= 11.4
    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=BashCommand(
                    name="odbc_to_mariadb_repo",
                    cmd="""
    file=$(echo mariadb-connector-odbc-*-src.tar.gz)
    version=${file#*-odbc-}
    version=${version%%-src.tar.gz}
    odbc_version=$(echo "$version" | cut -d. -f1,2)

    if [[ $odbc_version == 3.1 ]]; then
        echo 10.11
    else
        echo 11.8
    fi
    """,
                ),
                property="odbc_to_mariadb_repo",
            ),
            docker_environment=config,
        ),
    )

    sequence.add_step(
        InContainer(
            PropFromShellStep(
                command=BashCommand(
                    name="odbc_version",
                    cmd="""
    file=$(echo mariadb-connector-odbc-*-src.tar.gz)
    version=${file#*-odbc-}
    version=${version%%-src.tar.gz}
    odbc_version=$(echo "$version" | cut -d. -f1,2)
    echo "$odbc_version"
    """,
                ),
                property="odbc_version",
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
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/%(prop:buildnumber)s",
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

    sequence.add_step(trigger.ConODBC())

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
                    repo_url="https://mirror.mariadb.org/repo/%(prop:odbc_to_mariadb_repo)s",
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
    # as the C/ODBC build needs to link to the system level library, hence installing from
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
                    repo_url="https://mirror.mariadb.org/yum/%(prop:odbc_to_mariadb_repo)s",
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
    and then run the ODBC basic test
    """
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupDEBRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/repo/%(prop:odbc_to_mariadb_repo)s",
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
    # by installing in a clean environment and running the ODBC basic test
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

    # libodbc1 (deb <=11), libodbc2 (deb 12+) is required to run the tests,
    # and is not part of the C/ODBC .deb requirements, hence installing unixodbc
    sequence.add_step(
        InContainer(
            ShellStep(
                command=BashCommand(
                    name="Test DEB - ODBC Basic",
                    workdir=PurePath(f"{deb_path}/test"),
                    cmd='apt-get install -y unixodbc && sed -i "s/localhost/$SIDECAR_HOST/" odbc.ini && export TEST_SERVER=$SIDECAR_HOST && ./odbc_basic',
                    user="root",
                ),
                env_vars=[
                    ("TEST_SKIP_UNSTABLE_TESTS", "1"),
                    ("ODBCINI", "./odbc.ini"),
                    ("ODBCSYSINI", "./"),
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                    ("TEST_DRIVER", "maodbc_test"),
                    ("TEST_DSN", "maodbc_test"),
                ],
                options=StepOptions(
                    description="DEB - Run ODBC basic test",
                    descriptionDone="DEB - ODBC basic test done",
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
    and then run the ODBC basic test
    """
    ### INIT
    sequence = BuildSequence()

    sequence.add_step(
        InContainer(
            ShellStep(
                command=SetupRPMRepo(
                    repo_name="mariadb",
                    repo_url="https://mirror.mariadb.org/yum/%(prop:odbc_to_mariadb_repo)s",
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
    # specified, by installing in a clean environment and running the ODBC basic test
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
                    name=f"{os_name}:Test ODBC Basic",
                    workdir=PurePath(f"{rpm_path}/test"),
                    cmd='sed -i "s/localhost/$SIDECAR_HOST/" odbc.ini && export TEST_SERVER=$SIDECAR_HOST && ./odbc_basic',
                    user="root",
                ),
                env_vars=[
                    ("TEST_SKIP_UNSTABLE_TESTS", "1"),
                    ("ODBCINI", "./odbc.ini"),
                    ("ODBCSYSINI", "./"),
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                    ("TEST_DRIVER", "maodbc_test"),
                    ("TEST_DSN", "maodbc_test"),
                ],
                options=StepOptions(
                    description=f"{os_name}:Run ODBC basic test",
                    descriptionDone=f"{os_name}:ODBC basic test done",
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
):
    sequence = BuildSequence()
    sequence.add_step(
        InContainer(
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="Bintar",
                    cmake_generator=CMakeGenerator(
                        source_path=source_path,
                        builddir=bintar_path,
                        use_ccache=True,
                        flags=[
                            CMakeOption(OTHER.CONC_WITH_UNIT_TESTS, False),
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.RELWITHDEBUG),
                            CMakeOption(
                                OTHER.PACKAGE_PLATFORM_SUFFIX, package_platform_suffix
                            ),
                        ],
                    ),
                ),
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
                    name="Test bintar - ODBC ctest",
                    workdir=PurePath(f"{bintar_path}/test"),
                    cmd='sed -i "s/localhost/$SIDECAR_HOST/" odbc.ini && export TEST_SERVER=$SIDECAR_HOST && ctest --output-on-failure',
                ),
                env_vars=[
                    ("TEST_SKIP_UNSTABLE_TESTS", "1"),
                    ("ODBCINI", "./odbc.ini"),
                    ("ODBCSYSINI", "./"),
                    ("TEST_UID", "root"),
                    ("TEST_PASSWORD", ""),
                    ("TEST_PORT", "3306"),
                    ("TEST_SCHEMA", "test"),
                    ("TEST_VERBOSE", "true"),
                    ("TEST_DRIVER", "maodbc_test"),
                    ("TEST_DSN", "maodbc_test"),
                ],
                options=StepOptions(
                    description="Bintar - Run ODBC ctest",
                    descriptionDone="Bintar - ODBC ctest done",
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
                    url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/%(prop:tarbuildnum)s/%(prop:buildername)s",
                    url_text="Packages",
                ),
            ),
            docker_environment=config,
        )
    )
    return sequence
