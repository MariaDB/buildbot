import os
from pathlib import PurePath

from configuration.builders.infra.runtime import InContainer
from configuration.steps.base import StepOptions
from configuration.steps.commands.base import URL
from configuration.steps.commands.mtr import MTRReporter, MTRTest
from configuration.steps.commands.util import (
    CreateS3Bucket,
    DeleteS3Bucket,
    SaveCompressedTar,
)
from configuration.steps.generators.mtr.generator import MTRGenerator
from configuration.steps.generators.mtr.options import (
    MTR,
    SUITE,
    MTROption,
    TestSuiteCollection,
)
from configuration.steps.master import MasterShellStep
from configuration.steps.remote import ShellStep
from utils import hasFailed

MTR_PATH_TO_SAVE_LOGS = PurePath("/home/buildbot/mtr/logs")


def get_mtr_normal_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
    additional_mtr_options: list[MTROption] = [],
    env_vars: list[tuple] = [],
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
                            MTROption(MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "nm.xml"),
                        ]
                        + additional_mtr_options,
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR normal"
                ),
                env_vars=env_vars,
            )
        )
    )
    return steps


def get_mtr_rocksdb_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
    additional_mtr_options: list[MTROption] = [],
    env_vars: list[tuple] = [],
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
                            MTROption(
                                MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "rocksdb.xml"
                            ),
                        ]
                        + additional_mtr_options,
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR rocksdb"
                ),
                env_vars=env_vars,
            )
        )
    )
    return steps


def get_mtr_galera_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
    additional_mtr_options: list[MTROption] = [],
    env_vars: list[tuple] = [],
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
                            MTROption(
                                MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "galera.xml"
                            ),
                        ]
                        + additional_mtr_options,
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
                env_vars=env_vars,
            )
        )
    )
    return steps


def get_mtr_spider_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
    additional_mtr_options: list[MTROption] = [],
    env_vars: list[tuple] = [],
):
    steps = []
    steps.append(
        step_wrapping_fn(
            ShellStep(
                MTRTest(
                    name="spider",
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "spider",
                    workdir=path_to_test_runner,
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 2),
                            MTROption(MTR.MAX_SAVE_DATADIR, 10),
                            MTROption(MTR.MAX_TEST_FAIL, 20),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/spider"),
                            MTROption(
                                MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "spider.xml"
                            ),
                        ]
                        + additional_mtr_options,
                        suite_collection=TestSuiteCollection(
                            [
                                SUITE.SPIDER,
                                SUITE.SPIDER_BG,
                                SUITE.SPIDER_BUGFIX,
                                SUITE.SPIDER_FEATURE,
                                SUITE.SPIDER_REGRESSION_E1121,
                                SUITE.SPIDER_REGRESSION_E112122,
                            ]
                        ),
                    ),
                ),
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR spider"
                ),
                env_vars=env_vars,
            )
        )
    )
    return steps


def get_mtr_s3_steps(
    jobs,
    path_to_test_runner: PurePath,
    halt_on_failure: bool = True,
    step_wrapping_fn=lambda step: step,
    additional_mtr_options: list[MTROption] = [],
    env_vars: list[tuple] = [],
):
    steps = []
    steps.append(
        MasterShellStep(
            command=CreateS3Bucket(bucket=f"%(prop:buildername)s-%(prop:buildnumber)s")
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
                            MTROption(MTR.XML_REPORT, MTR_PATH_TO_SAVE_LOGS / "s3.xml"),
                        ]
                        + additional_mtr_options,
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
                ]
                + env_vars,
                options=StepOptions(
                    haltOnFailure=halt_on_failure, descriptionDone="MTR S3"
                ),
            )
        )
    )
    steps.append(
        MasterShellStep(
            command=DeleteS3Bucket(bucket=f"%(prop:buildername)s-%(prop:buildnumber)s"),
            options=StepOptions(alwaysRun=True),
        ),
    )
    return steps


def add_test_suites_steps(
    jobs,
    config,
    MTR_RUNNER_PATH=PurePath("mysql-test"),
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
        save_mtr_logs(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    )

    steps.append(
        mtr_reporter(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    )

    return steps


def save_mtr_logs(
    mtr_logs_path: PurePath = PurePath("mtr"),
    step_wrapping_fn=lambda step: step,
):
    return step_wrapping_fn(
        ShellStep(
            command=SaveCompressedTar(
                name="Save failed MTR logs",
                workdir=mtr_logs_path,
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


def mtr_reporter(
    step_wrapping_fn=lambda step: step,
):
    return step_wrapping_fn(
        ShellStep(
            command=MTRReporter(
                workdir=PurePath("mtr/logs"),
            ),
            url=URL(
                url=f"{os.environ['BUILDMASTER_URL']}/cr",
                url_text="Test results",
            ),
            options=StepOptions(
                alwaysRun=True, doStepIf=(lambda step: hasFailed(step))
            ),
            warn_on_fail=True,
        ),
    )
