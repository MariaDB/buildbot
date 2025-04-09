from configuration.builders.infra.runtime import BuildSequence, RunInContainer
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
from configuration.steps.local import MasterShellStep
from configuration.steps.remote import DockerShellStep, PropFromShellStep, ShellStep
from constants import SAVED_PACKAGE_BRANCHES
from utils import hasFailed, hasPackagesGenerated, savePackageIfBranchMatch

MTR_PATH_TO_SAVE_LOGS = "/home/buildbot/mtr/logs"


def deb_autobake(
    config,
    jobs,
    buildername,
    artifacts_url,
    test_galera=False,
    test_rocksdb=False,
    test_s3=False,
):
    # INIT
    prepare_steps = []
    active_steps = []
    cleanup_steps = []
    in_container_steps = []

    sequence = BuildSequence(
        prepare_steps=prepare_steps,
        active_steps=active_steps,
        cleanup_steps=cleanup_steps,
    )

    in_container_steps.extend(
        [
            ShellStep(command=FetchTarball(workdir="build/debian")),
            ShellStep(
                command=CompileDebAutobake(workdir="build/debian"),
                env_vars=[
                    ("DEB_BUILD_OPTIONS", "parallel=%s" % jobs),
                ],
            ),
            PropFromShellStep(
                command=FindFiles(
                    include="*",
                    workdir="build",
                ),
                property="packages",
            ),
            DockerShellStep(
                command=CreateDebRepo(
                    url=artifacts_url,
                    buildername=buildername,
                    workdir="build",
                ),
                checkpoint=True,
            ),
            DockerShellStep(
                command=InstallDEB(workdir="build/debs", packages_file="Packages"),
                checkpoint=True,
            ),
        ]
    )

    add_normal_test(
        active_steps=in_container_steps,
        jobs=jobs,
        path_to_test_runner="/usr/share/mariadb/mariadb-test",
        halt_on_failure=False,
    )

    if test_s3:
        add_S3_test(
            buildername=buildername,
            prepare_steps=prepare_steps,
            active_steps=in_container_steps,
            cleanup_steps=cleanup_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb/mariadb-test",
            halt_on_failure=False,
        )

    if test_rocksdb:
        add_rocksdb_test(
            active_steps=in_container_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb/mariadb-test",
            halt_on_failure=False,
        )

    if test_galera:
        add_galera_test(
            active_steps=in_container_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb/mariadb-test",
            halt_on_failure=False,
        )

    in_container_steps.extend(
        [
            ShellStep(
                command=SavePackages(
                    packages=["mariadb.sources", "debs"],
                    workdir="build",
                ),
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(step)
                        and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
                    )
                ),
            ),
            ShellStep(
                command=SaveCompressedTar(
                    name="Save failed MTR logs",
                    workdir="/home/buildbot/mtr",
                    archive_name="logs",
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                options=StepOptions(
                    alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
                ),
            ),
        ]
    )

    RunInContainer(
        build_sequence=sequence,  # Will update sequence prepare/active/cleanup steps
        container_config=config,
        active_steps=in_container_steps,
        buildername=buildername,
    ).generate()

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

    # INIT
    prepare_steps = []
    active_steps = []
    cleanup_steps = []
    # Keep in container steps separate and merge later using RunInContainer
    in_container_steps = []

    sequence = BuildSequence(
        prepare_steps=prepare_steps,
        active_steps=active_steps,
        cleanup_steps=cleanup_steps,
    )

    if has_compat:
        in_container_steps.append(
            ShellStep(
                command=FetchCompat(
                    rpm_type=rpm_type,
                    arch=arch,
                    url=artifacts_url,
                    workdir="",
                ),
            )
        )
    in_container_steps.extend(
        [
            ShellStep(
                FetchTarball(workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX")
            ),
            ShellStep(
                command=ConfigureMariaDBCMake(
                    name="mysql_release",
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=[
                            CMakeOption(OTHER.BUILD_CONFIG, BuildConfig.MYSQL_RELEASE),
                            CMakeOption(OTHER.RPM, rpm_type),
                        ],
                    ),
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                )
            ),
            ShellStep(
                CompileMakeCommand(
                    option=MAKE.COMPILE,
                    jobs=jobs,
                    verbose=False,
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                )
            ),
            ShellStep(
                CompileMakeCommand(
                    option=MAKE.PACKAGE,
                    jobs=jobs,
                    verbose=False,
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                )
            ),
            ShellStep(
                CompileMakeCommand(
                    option=MAKE.SOURCE,
                    jobs=jobs,
                    verbose=False,
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                )
            ),
            PropFromShellStep(
                command=FindFiles(
                    include="*.rpm",
                    exclude="*.src.rpm",
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                ),
                property="packages",
            ),
            DockerShellStep(
                command=InstallRPMFromProp(
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                    property_name="packages",
                ),
                checkpoint=True,
            ),
        ]
    )

    # Add in container MTR tests
    add_normal_test(
        active_steps=in_container_steps,  # Will append to in_container_steps
        jobs=jobs,
        path_to_test_runner="/usr/share/mariadb-test",  # Run from Installed Tree
        halt_on_failure=False,
    )

    if test_s3:
        add_S3_test(
            buildername=buildername,
            prepare_steps=prepare_steps,
            active_steps=in_container_steps,
            cleanup_steps=cleanup_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb-test",
            halt_on_failure=False,
        )

    if test_rocksdb:
        add_rocksdb_test(
            active_steps=in_container_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb-test",
            halt_on_failure=False,
        )

    if test_galera:
        add_galera_test(
            active_steps=in_container_steps,
            jobs=jobs,
            path_to_test_runner="/usr/share/mariadb-test",
            halt_on_failure=False,
        )

    # ... continue adding in container steps
    in_container_steps.extend(
        [
            ShellStep(
                command=CreateRpmRepo(
                    rpm_type=rpm_type,
                    url=artifacts_url,
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                ),
            ),
            ShellStep(
                command=SavePackages(
                    packages=["MariaDB.repo", "rpms", "srpms"],
                    workdir="padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX",
                    destination="/packages/%(prop:tarbuildnum)s/%(prop:buildername)s",
                ),
                options=StepOptions(
                    doStepIf=(
                        lambda step: hasPackagesGenerated(step)
                        and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
                    )
                ),
            ),
            ShellStep(
                command=SaveCompressedTar(
                    name="Save failed MTR logs",
                    workdir="/home/buildbot/mtr",
                    archive_name="logs",
                    destination="/packages/%(prop:tarbuildnum)s/logs/%(prop:buildername)s",
                ),
                options=StepOptions(
                    alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
                ),
            ),
        ]
    )

    # Add in container steps to the build sequence
    RunInContainer(
        build_sequence=sequence,
        container_config=config,
        active_steps=in_container_steps,
        buildername=buildername,
    ).generate()

    return sequence


def add_normal_test(
    active_steps,
    jobs,
    path_to_test_runner: str,
    halt_on_failure: bool = True,
):
    active_steps.append(
        ShellStep(
            MTRTest(
                name="normal",
                save_logs_path=f"{MTR_PATH_TO_SAVE_LOGS}/normal",
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


def add_rocksdb_test(
    active_steps,
    jobs,
    path_to_test_runner: str,
    halt_on_failure: bool = True,
):
    active_steps.append(
        ShellStep(
            MTRTest(
                name="rocksdb",
                save_logs_path=f"{MTR_PATH_TO_SAVE_LOGS}/rocksdb",
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


def add_galera_test(
    active_steps,
    jobs,
    path_to_test_runner: str,
    halt_on_failure: bool = True,
):
    active_steps.append(
        ShellStep(
            MTRTest(
                name="galera",
                save_logs_path=f"{MTR_PATH_TO_SAVE_LOGS}/galera",
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


def add_S3_test(
    buildername,
    prepare_steps,
    active_steps,
    cleanup_steps,
    jobs,
    path_to_test_runner: str,
    halt_on_failure: bool = True,
):
    prepare_steps.append(
        MasterShellStep(
            command=CreateS3Bucket(bucket=f"{buildername}-%(prop:buildnumber)s")
        ).generate()
    )

    active_steps.append(
        ShellStep(
            command=MTRTest(
                name="S3",
                save_logs_path=f"{MTR_PATH_TO_SAVE_LOGS}/s3",
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
    cleanup_steps.append(
        MasterShellStep(
            command=DeleteS3Bucket(bucket=f"{buildername}-%(prop:buildnumber)s"),
            options=StepOptions(alwaysRun=True),
        ).generate(),
    )


# TODO (Razvan): Future implementations
def bintar(): ...
def docker_library(): ...
def release_preparation(): ...
