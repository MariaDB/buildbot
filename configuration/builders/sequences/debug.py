from pathlib import PurePath

from configuration.builders.infra.runtime import BuildSequence, InContainer
from configuration.builders.sequences.helpers import save_mtr_logs
from configuration.steps.base import StepOptions
from configuration.steps.commands.compile import MAKE, CompileMakeCommand
from configuration.steps.commands.configure import ConfigureMariaDBCMake
from configuration.steps.commands.download import FetchTarball
from configuration.steps.commands.mtr import MTRTest
from configuration.steps.commands.util import (
    AnyCommand,
    PrintEnvironmentDetails,
    UBIEnableFIPS,
)
from configuration.steps.generators.cmake.generator import CMakeGenerator
from configuration.steps.generators.cmake.options import (
    CMAKE,
    PLUGIN,
    WITH,
    BuildType,
    CMakeOption,
)
from configuration.steps.generators.mtr.generator import MTRGenerator
from configuration.steps.generators.mtr.options import MTR, MTROption
from configuration.steps.remote import ShellStep

MTR_PATH_TO_SAVE_LOGS = PurePath("/home/buildbot/mtr/logs")


def openssl_fips(
    config,
    jobs,
):
    ### INIT
    sequence = BuildSequence()

    ### ADD STEPS
    sequence.add_step(ShellStep(command=PrintEnvironmentDetails()))

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=True,
            step=ShellStep(
                command=UBIEnableFIPS(),
                options=StepOptions(descriptionDone="Enable FIPS mode"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            container_commit=False,
            step=ShellStep(
                command=FetchTarball(),
                options=StepOptions(descriptionDone="Fetch tarball"),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=ConfigureMariaDBCMake(
                    name="debug",
                    cmake_generator=CMakeGenerator(
                        use_ccache=True,
                        flags=[
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG),
                            CMakeOption(WITH.SSL, "system"),
                            CMakeOption(PLUGIN.ROCKSDB_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.SPHINX_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.SPIDER_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.MROONGA_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.TOKUDB_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.FEDERATED_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.FEDERATEDX_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.COLUMNSTORE_STORAGE_ENGINE, False),
                            CMakeOption(PLUGIN.CONNECT_STORAGE_ENGINE, False),
                        ],
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
                command=CompileMakeCommand(
                    option=MAKE.COMPILE,
                    jobs=jobs,
                    verbose=False,
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
                command=AnyCommand(
                    name="Check if libcrypto is dynamically linked",
                    command="""
                            ldd ./client/mariadb | grep libcrypto
                            ldd ./sql/mariadbd | grep libcrypto""",
                ),
                options=StepOptions(
                    descriptionDone="Check if libcrypto is dynamically linked"
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                command=AnyCommand(
                    name="Extract tests to run",
                    command="""
                            set +x

                            extract_test() {
                            local filepath="$1"

                            awk -F'/' -v path="$filepath" '
                            BEGIN {
                                n = split(path, parts, "/")
                                test = parts[n]
                                sub(/\.test$/, "", test)
                                dir1 = parts[n-1]
                                if (dir1 == "t") {
                                suite = parts[n-2]
                                } else {
                                suite = dir1
                                }
                                print suite "." test
                            }
                            '
                            }

                            tests_to_run="mysql-test/tests_to_run.txt"

                            # Extract all encryption tests
                            find mysql-test/suite/encryption -type f -name "*.test" | while read -r file; do
                            extract_test "$file" >> $tests_to_run
                            done

                            # Extract all tests having SSL in their name
                            find mysql-test -name "*ssl*.test" | while read -r file; do
                            extract_test "$file" >> $tests_to_run
                            done

                            # Extract all plugin tests
                            find plugin/**/* -name "*.test" | while read -r file; do
                            extract_test "$file" >> $tests_to_run
                            done

                            # Extract all tests related to encoding, encryption, and hashing
                            grep -rliE --include="*.test" 'encode|des_encrypt|aes_encrypt|md5|sha[12]' mysql-test | while read -r file; do
                            extract_test "$file" >> $tests_to_run
                            done

                            # Sort and remove duplicates
                            sort -u "$tests_to_run" -o "$tests_to_run"

                            cat $tests_to_run
                        """,
                ),
                options=StepOptions(
                    descriptionDone="Extract tests to run",
                ),
            ),
        )
    )

    sequence.add_step(
        InContainer(
            docker_environment=config,
            step=ShellStep(
                MTRTest(
                    name="FIPS",
                    tests_from_file=PurePath("./tests_to_run.txt"),
                    save_logs_path=MTR_PATH_TO_SAVE_LOGS / "FIPS",
                    testcase=MTRGenerator(
                        flags=[
                            MTROption(MTR.VERBOSE_RESTART, True),
                            MTROption(MTR.FORCE, True),
                            MTROption(MTR.RETRY, 3),
                            MTROption(MTR.MAX_SAVE_CORE, 2),
                            MTROption(MTR.MAX_SAVE_DATADIR, 1),
                            MTROption(MTR.MAX_TEST_FAIL, 20),
                            MTROption(MTR.PARALLEL, jobs * 2),
                            MTROption(MTR.VARDIR, "/dev/shm/fips"),
                        ],
                    ),
                ),
                options=StepOptions(haltOnFailure=True, descriptionDone="MTR FIPS"),
            ),
        )
    )

    sequence.add_step(
        save_mtr_logs(
            step_wrapping_fn=lambda step: InContainer(
                docker_environment=config, step=step
            ),
        )
    )

    return sequence
