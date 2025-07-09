import os
from pathlib import PurePath

from configuration.builders.infra.runtime import BuildSequence, InContainer
from configuration.builders.sequences.helpers import add_test_suites_steps
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL
from configuration.steps.commands.compile import (
    MAKE,
    CompileDebAutobake,
    CompileMakeCommand,
)
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchCompat, FetchTarball
from configuration.steps.commands.packages import (
    CreateDebRepo,
    CreateRpmRepo,
    InstallDEB,
    InstallRPMFromProp,
    SavePackages,
)
from configuration.steps.commands.util import FindFiles, PrintEnvironmentDetails
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import OTHER, BuildConfig, CMakeOption
from configuration.steps.remote import PropFromShellStep, ShellStep
from constants import SAVED_PACKAGE_BRANCHES
from utils import hasFailed, hasPackagesGenerated, savePackageIfBranchMatch


def deb_autobake(
    config,
    jobs,
    artifacts_url,
    test_galera=False,
    test_rocksdb=False,
    test_s3=False,
):
    ### INIT
    MTR_RUNNER_PATH = PurePath("/usr/share/mariadb/mariadb-test")
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=FetchTarball(workdir=PurePath("build/debian")),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        ),
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileDebAutobake(workdir=PurePath("build/debian")),
                env_vars=[
                    ("DEB_BUILD_OPTIONS", "parallel=%s" % jobs),
                ],
                options=StepOptions(descriptionDone="Compile DEB autobake"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=PropFromShellStep(
                command=FindFiles(
                    include="*",
                    workdir=PurePath("build"),
                ),
                property="packages",
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=CreateDebRepo(
                    url=artifacts_url,
                    workdir=PurePath("build"),
                ),
                options=StepOptions(descriptionDone="Create DEB repository"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=InstallDEB(
                    workdir=PurePath("build/debs"), packages_file="Packages"
                ),
                options=StepOptions(descriptionDone="Install DEB packages"),
            ),
        )
    )

    ## ADD MTR TESTS
    for step in add_test_suites_steps(
        jobs=jobs,
        MTR_RUNNER_PATH=MTR_RUNNER_PATH,
        config=config,
        test_galera=test_galera,
        test_rocksdb=test_rocksdb,
        test_s3=test_s3,
    ):
        sequence.add_step(step)

    ## POST-TEST STEPS
    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SavePackages(
                    packages=["mariadb.sources", "debs"],
                    workdir=PurePath("build"),
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/%(prop:tarbuildnum)s/%(prop:buildername)s",
                    url_text="DEB packages",
                ),
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(
                            step
                        )  # Run only if packages were generated
                        and savePackageIfBranchMatch(
                            step, SAVED_PACKAGE_BRANCHES
                        )  # We don't save packages for Pull Requests or bb branches
                        and not hasFailed(
                            step
                        )  # Any failed step will mark the build as failed so don't save packages
                    )
                ),
            ),
        )
    )

    return sequence


def rpm_autobake(
    config,
    jobs,
    rpm_type,
    arch,
    artifacts_url,
    has_compat=False,
    test_galera=False,
    test_rocksdb=False,
    test_s3=False,
):

    ### INIT
    RPM_AUTOBAKE_BASE_WORKDIR = PurePath(
        "padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX"
    )
    MTR_RUNNER_PATH = PurePath("/usr/share/mariadb-test")
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    if has_compat:
        sequence.add_step(
            InContainer(
                docker_environment=config,
                step=ShellStep(
                    command=FetchCompat(
                        rpm_type=rpm_type,
                        arch=arch,
                        url=artifacts_url,
                    ),
                ),
            )
        )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=False,
            step=ShellStep(
                command=FetchTarball(workdir=RPM_AUTOBAKE_BASE_WORKDIR),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=ConfigureMariaDBCMake(
                    name="mysql_release",
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=[
                            CMakeOption(OTHER.BUILD_CONFIG, BuildConfig.MYSQL_RELEASE),
                            CMakeOption(OTHER.RPM, rpm_type),
                        ],
                    ),
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
                options=StepOptions(descriptionDone="Configure"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileMakeCommand(
                    option=MAKE.PACKAGE_SOURCE,
                    jobs=jobs,
                    verbose=False,
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
                options=StepOptions(descriptionDone="MAKE source package"),
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
                    verbose=False,
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                    output_sync=True,
                ),
                options=StepOptions(descriptionDone="MAKE compile"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileMakeCommand(
                    option=MAKE.PACKAGE,
                    jobs=jobs,
                    verbose=False,
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
                options=StepOptions(descriptionDone="MAKE package"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=PropFromShellStep(
                command=FindFiles(
                    include="*.rpm",
                    exclude="*.src.rpm",
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
                property="packages",
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=InstallRPMFromProp(
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                    property_name="packages",
                ),
                options=StepOptions(descriptionDone="Install RPM packages"),
            ),
        )
    )

    ## ADD MTR TESTS
    for step in add_test_suites_steps(
        jobs=jobs,
        MTR_RUNNER_PATH=MTR_RUNNER_PATH,
        config=config,
        test_galera=test_galera,
        test_rocksdb=test_rocksdb,
        test_s3=test_s3,
    ):
        sequence.add_step(step)

    ## POST-TEST STEPS
    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=CreateRpmRepo(
                    rpm_type=rpm_type,
                    url=artifacts_url,
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SavePackages(
                    packages=["MariaDB.repo", "rpms", "srpms"],
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                    destination="/packages/%(prop:tarbuildnum)s/%(prop:buildername)s",
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/%(prop:tarbuildnum)s/%(prop:buildername)s",
                    url_text="RPM packages",
                ),
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(
                            step
                        )  # Run only if packages were generated
                        and savePackageIfBranchMatch(
                            step, SAVED_PACKAGE_BRANCHES
                        )  # We don't save packages for Pull Requests or bb branches
                        and not hasFailed(
                            step
                        )  # Any failed step will mark the build as failed so don't save packages
                    )
                ),
            ),
        )
    )

    return sequence


# # TODO (Razvan): Future implementations
# def bintar(): ...
# def docker_library(): ...
# def release_preparation(): ...
