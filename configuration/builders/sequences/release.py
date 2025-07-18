import os
from pathlib import PurePath

from configuration.builders.infra.runtime import BuildSequence, InContainer
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL
from configuration.steps.commands.compile import (
    MAKE,
    CompileDebAutobake,
    CompileMakeCommand,
)
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchCompat, FetchTarball
from configuration.steps.commands.mtr import MTRTest
from configuration.steps.commands.packages import (
    CreateDebRepo,
    CreateRpmRepo,
    InstallDEB,
    InstallRPMFromProp,
    SavePackages,
)
from configuration.steps.commands.util import (
    CreateS3Bucket,
    DeleteS3Bucket,
    FindFiles,
    PrintEnvironmentDetails,
    SaveCompressedTar,
)
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import OTHER, BuildConfig, CMakeOption
from configuration.steps.generators.mtr.generator import MTRGenerator
from configuration.steps.generators.mtr.options import (
    MTR,
    SUITE,
    MTROption,
    TestSuiteCollection,
)
from configuration.steps.master import MasterShellStep
from configuration.steps.remote import PropFromShellStep, ShellStep
from constants import SAVED_PACKAGE_BRANCHES
from utils import hasFailed, hasPackagesGenerated, savePackageIfBranchMatch

MTR_PATH_TO_SAVE_LOGS = PurePath("/home/buildbot/mtr/logs")


def deb_autobake(
    config,
    jobs,
    buildername,
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
                    buildername=buildername,
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
        buildername=buildername,
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
    buildername,
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
        buildername=buildername,
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


## ------------------------------------------------------------------- ##
##                        HELPER FUNCTIONS                             ##
## ------------------------------------------------------------------- ##


def get_mtr_normal_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
):
    steps = []
    steps.append(
        step_wrapping_fn(
            ShellStep(
                MTRTest(
                    name="normal",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "normal",
                    workdir=path_to_test_runner,
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 2),
                            MTROption(MTR.MAX_SAVE_DATADIR, 1),
                            MTROption(MTR.MAX_TEST_FAIL, 20),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/normal"),
                        ],
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR normal"
                ),
            )
        )
    )
    return steps


def get_mtr_rocksdb_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
):
    steps = []
    steps.append(
        step_wrapping_fn(
            ShellStep(
                MTRTest(
                    name="rocksdb",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "rocksdb",
                    workdir=path_to_test_runner,
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 1),
                            MTROption(MTR.MAX_SAVE_DATADIR, 1),
                            MTROption(MTR.MAX_TEST_FAIL, 3),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/rocksdb"),
                            MTROption(MTR.SUITE, "rocksdb*"),
                            MTROption(MTR.SKIP_TEST, "rocksdb_hotbackup*"),
                        ],
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR rocksdb"
                ),
            )
        )
    )
    return steps


def get_mtr_galera_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
):
    steps = []
    steps.append(
        step_wrapping_fn(
            ShellStep(
                MTRTest(
                    name="galera",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "galera",
                    workdir=path_to_test_runner,
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 2),
                            MTROption(MTR.MAX_SAVE_DATADIR, 10),
                            MTROption(MTR.MAX_TEST_FAIL, 20),
                            MTROption(MTR.BIG_TEST, True),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/galera"),
                        ],
                        suite_collection=TestSuiteCollection(
                            [
                                SUITE.WSREP,
                                SUITE.GALERA,
                                SUITE.GALERA_3NODES,
                                SUITE.GALERA_3NODES_SR,
                            ]
                        ),
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR galera"
                ),
            )
        )
    )
    return steps


def get_mtr_s3_steps(
    buildername,
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
):
    steps = []
    steps.append(
        MasterShellStep(
            command=CreateS3Bucket(bucket=f"{buildername}-%(prop:buildnumber)s")
        )
    )

    steps.append(
        step_wrapping_fn(
            ShellStep(
                command=MTRTest(
                    name="S3",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "s3",
                    workdir=path_to_test_runner,
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 1),
                            MTROption(MTR.MAX_SAVE_DATADIR, 1),
                            MTROption(MTR.MAX_TEST_FAIL, 3),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/s3"),
                            MTROption(MTR.SUITE, "s3"),
                        ],
                    ),
                ),
                env_vars=[
                    ("S3_HOST_NAME", "minio.mariadb.org"),
                    ("S3_PORT", "443"),
                    ("S3_ACCESS_KEY", "%(secret:minio_access_key)s"),
                    ("S3_SECRET_KEY", "%(secret:minio_secret_key)s"),
                    ("S3_BUCKET", "%(prop:buildername)s-%(prop:buildnumber)s"),
                    ("S3_USE_HTTPS", "OFF"),
                    ("S3_PROTOCOL_VERSION", "Path"),
                ],
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR S3"
                ),
            )
        )
    )
    steps.append(
        MasterShellStep(
            command=DeleteS3Bucket(bucket=f"{buildername}-%(prop:buildnumber)s"),
            options=StepOptions(alwaysRun=True),
        ),
    )
    return steps


def add_test_suites_steps(
    jobs,
    MTR_RUNNER_PATH,
    config,
    buildername,
    test_galera=False,
    test_rocksdb=False,
    test_s3=False,
):
    steps = []
    steps.extend(
        get_mtr_normal_steps(
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    )
    if test_s3:
        steps.extend(
            get_mtr_s3_steps(
                buildername=buildername,
                jobs=jobs,
                path_to_test_runner=MTR_RUNNER_PATH,
                halt_on_failure=False,
                step_wrapping_fn=lambda step: InContainer(
                    docker_environment=config, step=step
                ),
            )
        )
    if test_rocksdb:
        steps.extend(
            get_mtr_rocksdb_steps(
                jobs=jobs,
                path_to_test_runner=MTR_RUNNER_PATH,
                halt_on_failure=False,
                step_wrapping_fn=lambda step: InContainer(
                    docker_environment=config, step=step
                ),
            )
        )
    if test_galera:
        steps.extend(
            get_mtr_galera_steps(
                jobs=jobs,
                path_to_test_runner=MTR_RUNNER_PATH,
                halt_on_failure=False,
                step_wrapping_fn=lambda step: InContainer(
                    docker_environment=config, step=step
                ),
            )
        )

    steps.append(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SaveCompressedTar(
                    name="Save failed MTR logs",
                    workdir=PurePath("mtr"),
                    archive_name="logs",
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                url=URL(
                    url=f"{os.environ['ARTIFACTS_URL']}/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                    url_text="MTR logs",
                ),
                options=StepOptions(
                    alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
                ),
            ),
        )
    )

    return steps


# # TODO (Razvan): Future implementations
# def bintar(): ...
# def docker_library(): ...
# def release_preparation(): ...
