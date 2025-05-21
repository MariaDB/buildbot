from pathlib import PurePath

from configuration.builders.infra.runtime import BuildSequence, InContainer
from configuration.steps.base import StepOptions
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
            ),
        )
    )

    ## ADD MTR TESTS
    # Add normal MTR tests
    for step in get_mtr_normal_steps(
        jobs=jobs,
        path_to_test_runner=MTR_RUNNER_PATH,
        halt_on_failure=False,
        step_wrapping_fn=lambda step: InContainer(docker_environment=config, step=step),
    ):
        sequence.add_step(step)

    # Add S3 MTR tests
    if test_s3:
        for step in get_mtr_s3_steps(
            buildername=buildername,
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ):
            sequence.add_step(step)

    # Add rocksdb MTR tests
    if test_rocksdb:
        for step in get_mtr_rocksdb_steps(
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ):
            sequence.add_step(step)

    # Add galera MTR tests
    if test_galera:
        for step in get_mtr_galera_steps(
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
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
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(step)
                        and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
                    )
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SaveCompressedTar(
                    name="Save failed MTR logs",
                    workdir=PurePath("mtr"),
                    archive_name="logs",
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                options=StepOptions(
                    alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
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
                ),
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
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=CompileMakeCommand(
                    option=MAKE.SOURCE,
                    jobs=jobs,
                    verbose=False,
                    workdir=RPM_AUTOBAKE_BASE_WORKDIR,
                ),
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
            ),
        )
    )

    ## ADD MTR TESTS
    # Add normal MTR tests
    for step in get_mtr_normal_steps(
        jobs=jobs,
        path_to_test_runner=MTR_RUNNER_PATH,
        halt_on_failure=False,
        step_wrapping_fn=lambda step: InContainer(docker_environment=config, step=step),
    ):
        sequence.add_step(step)

    # Add S3 MTR tests
    if test_s3:
        for step in get_mtr_s3_steps(
            buildername=buildername,
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ):
            sequence.add_step(step)

    # Add rocksdb MTR tests
    if test_rocksdb:
        for step in get_mtr_rocksdb_steps(
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        ):
            sequence.add_step(step)

    # Add galera MTR tests
    if test_galera:
        for step in get_mtr_galera_steps(
            jobs=jobs,
            path_to_test_runner=MTR_RUNNER_PATH,
            halt_on_failure=False,
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
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
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(step)
                        and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
                    )
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=SaveCompressedTar(
                    name="Save failed MTR logs",
                    workdir=PurePath("mtr"),
                    archive_name="logs",
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                options=StepOptions(
                    alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
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
                options=StepOptions(haltOnFailure=halt_on_failure),
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
                options=StepOptions(haltOnFailure=halt_on_failure),
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
                            MTROption(MTR.MAX_TEST_FAIL, 1),
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
                options=StepOptions(haltOnFailure=halt_on_failure),
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
                options=StepOptions(haltOnFailure=halt_on_failure),
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


# # TODO (Razvan): Future implementations
# def bintar(): ...
# def docker_library(): ...
# def release_preparation(): ...
