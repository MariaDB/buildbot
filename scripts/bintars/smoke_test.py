import argparse
import logging
import os
import re
import shutil
import sys
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import docker
import yaml
from common import GREEN, RED, prepare_test_directory, setup_logging
from docker.models.containers import Container


@dataclass
class MariaDBContainerRunner:
    # Helper class so we don't have to carry around too many
    # parameters for `docker run` and `docker exec` calls.
    image: str
    client: docker.DockerClient
    volumes: Tuple[Path, Path, bool]
    workdir: Path
    # Containers names will have this prefix when started via run_in_container.
    # This is useful to allow the caller of this script to know what to
    # clean up.
    name_prefix: str

    def run_in_container(
        self, command: list[str], wait: bool = True
    ) -> Tuple[int, str] | Container:
        # All volumes are rw.
        container = self.client.containers.run(
            self.image,
            name=f"{self.name_prefix}_{uuid.uuid4()}",
            working_dir=str(self.workdir),
            command=command,
            volumes={
                str(host_path): {
                    "bind": str(container_path),
                    "mode": "rw" if read_write else "ro",
                }
                for host_path, container_path, read_write in self.volumes
            },
            detach=True,
        )

        if not wait:
            return container

        output = ""
        # Wait for the container to finish and get logs
        logs = container.logs(stream=True)
        for line in logs:
            output += line.decode("utf-8").strip() + "\n"

        exit_code = container.wait()
        container.remove()
        return exit_code["StatusCode"], output

    def exec_in_container(self, container: Container, command: list[str]):
        return container.exec_run(cmd=command, workdir=str(self.workdir))


@dataclass(order=True)
class TestResult:
    # Container for a smoke test.
    failed: bool  # True if there were any errors.
    name: str  # Name of the test (image file tested)
    logs: list[str]  # Logs of the run

    def __repr__(self):
        return self.name


# Log levels
INFO = 1
ERROR = 2
EXCEPTION = 3


# Used to save logs in a list.
# We use it to be able to later print all logs for a particular thread,
# without having them intermixed with other threads.
def log(logs: list[int, str], level: int, string: str):
    logs.append((level, string))


def print_logs(logs: list[int, str]):
    for level, log_line in logs:
        if level == INFO:
            logging.info(log_line)
        if level == ERROR:
            logging.error(log_line)
        if level == EXCEPTION:
            logging.exception(log_line)


def run_test(
    container_name_prefix: str,
    files_path: Path,
    tests_path: Path,
    image: str,
    docker_client: docker.DockerClient,
) -> Tuple[bool, str, list[str]]:
    # We'll create the following folders in the tests_path.
    # <tests_dir>/./<archive>/ -> /binaries "ro"
    # <tests_dir>/./<image>/datadir -> /datadir "rw"
    # This organizes the test working files so we can mount them in containers
    # clearly.
    HOST_FILES_PATH = files_path
    CONT_BINARIES_PATH = Path("/binaries/")
    CONT_DATADIR_PATH = Path("/datadir/")
    # replace image ':' with '_' as part of volume name'
    HOST_DATADIR_PATH = tests_path / image.replace(":", "_") / "datadir"
    volumes = [
        (HOST_FILES_PATH.absolute(), CONT_BINARIES_PATH, False),
        (HOST_DATADIR_PATH.absolute(), CONT_DATADIR_PATH, True),
    ]

    logs = []
    runner = MariaDBContainerRunner(
        name_prefix=container_name_prefix,
        image=image,
        client=docker_client,
        volumes=volumes,
        workdir=CONT_BINARIES_PATH,
    )

    # Run the test in a Docker container
    try:
        if HOST_DATADIR_PATH.exists():
            # clean up HOST_DATADIR_PATH before running tests.
            # This is normally not needed, unless the script was interrupted
            # mid way or the previous cleanup failed.
            shutil.rmtree(str(HOST_DATADIR_PATH))

        log(logs, INFO, f"Pulling latest image of: {image}")
        docker_client.images.pull(image)

        mariadb_container: Container = None  # Define for finally block.
        log(logs, INFO, f"Testing mariadbd works on {image}")

        # Install the datadir.
        install_result, output = runner.run_in_container(
            command=[
                "./scripts/mariadb-install-db",
                f"--datadir={str(CONT_DATADIR_PATH)}",
            ]
        )

        if install_result:
            log(logs, ERROR, "Failed Datadir installation")
            log(logs, ERROR, f"\n{output}")
            return TestResult(failed=True, name=image, logs=logs)

        log(logs, INFO, "Starting mariadbd")
        mariadb_container: Container = runner.run_in_container(
            command=["./bin/mariadbd", f"--datadir={CONT_DATADIR_PATH}", "--user=root"],
            wait=False,
        )

        # Max 20 seconds for the server to be up.
        for i in range(10):
            exit_code, output = runner.exec_in_container(
                container=mariadb_container,
                command=["./bin/mariadb", "-e", "SELECT VERSION()"],
            )
            if exit_code == 0:
                log(logs, INFO, "Success")
                return TestResult(failed=False, name=image, logs=logs)
            time.sleep(2)

        log(logs, ERROR, "Failed running queries against MariaDB Server")
        log(logs, ERROR, f"Exit Code: {exit_code}")
        log(logs, ERROR, f"{output}")
    except Exception as e:
        log(logs, EXCEPTION, f"An error occurred while running the test: {e}")
    finally:
        try:
            if mariadb_container:
                mariadb_container.stop()
                status_code = mariadb_container.wait()
                if status_code["StatusCode"]:
                    log(logs, ERROR, status_code["StatusCode"])
                    output = ""
                    for line in mariadb_container.logs(stream=True):
                        output += line.decode("utf-8").strip()
                    log(logs, ERROR, output)
                mariadb_container.remove()
        except Exception:
            log(logs, EXCEPTION, f"Unable to clean up container {image}")

        try:
            if files_path:
                # Cleanup datadir for next run
                shutil.rmtree(str(HOST_DATADIR_PATH))
                log(logs, INFO, f"Cleaned up {str(HOST_DATADIR_PATH)}")
        except Exception:
            log(logs, EXCEPTION, f"Unable to clear {files_path} directories.")

    return TestResult(failed=True, name=image, logs=logs)


def wait_for_tests_to_complete(test_runs: Future) -> Tuple[TestResult, TestResult]:
    results: list[TestResult] = []
    completed = 0
    for test in as_completed(test_runs):
        completed += 1
        result: TestResult = test.result()
        msg = f"{RED}FAIL" if result.failed else f"{GREEN}PASS"
        logging.info(f"[{completed}/{len(test_runs)}]: {result.name} {msg}")
        results.append(test.result())

    passed = []
    failed = []
    for result in results:
        if result.failed:
            failed.append(result)
        else:
            passed.append(result)

    # Print failed test logs.
    for result in failed:
        logging.info(f"-------- {result.name:^20} --------")
        print_logs(result.logs)
    return passed, failed


# Clean up any leftover containers from previous run
def clean_up_containers(client: docker.DockerClient, prefix: str):
    running_containers: list[Container] = client.containers.list()
    for container in running_containers:
        if container.name.startswith(prefix):
            container.stop()
            container.remove()


def main(
    container_name_prefix: str,
    archive_path: Path,
    tests_path: Path,
    image_tests_file: str,
    docker_socket: str | None,
):
    files_path = None
    try:
        # Set up Docker client
        docker_client = docker.from_env()
        if docker_socket:
            docker_client = docker.DockerClient(base_url=docker_socket)

        clean_up_containers(docker_client, container_name_prefix)

        files_path, major_minor = prepare_test_directory(archive_path, tests_path)

        # Ensure files_path/bin/mariadbd exists
        mariadbd_path = Path(files_path).absolute() / "bin/mariadbd"
        if not mariadbd_path.exists():
            logging.error(f"{mariadbd_path} does not exist. Exiting.")
            sys.exit(1)

        logging.info(f"Using docker socket {docker_client.api.base_url}")

        with open(image_tests_file, "r") as f:
            test_list = yaml.safe_load(f)

        test_images = []
        for image in test_list:
            tag = image["tag"]
            pattern = image["re_version_filter"]
            if re.match(pattern, major_minor):
                test_images.append(tag)

        if not test_images:
            logging.error(f"No OSes re_version_filter matches {major_minor}")
            return 1

        # Run all tests using a ThreadPool. We are not CPU bound on the
        # python side as all we're doing is issuing a few docker commands.
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            test_runs = []
            for image in test_images:
                args = [
                    container_name_prefix,
                    files_path,
                    tests_path,
                    image,
                    docker_client,
                ]
                test_runs.append(executor.submit(run_test, *args))

            passed, failed = wait_for_tests_to_complete(test_runs)

        logging.info("------ TEST SUMMARY ------")
        logging.info(f"PASSED: {sorted(passed)}")
        if failed:
            logging.error(f"FAILED: {sorted(failed)}")
            return 1
        return 0

    except Exception as e:
        logging.exception(f"General failure: {e}")
        return 1
    finally:
        try:
            if files_path:
                shutil.rmtree(files_path.as_posix())
                logging.info(f"Cleaned up {files_path}")
        except Exception:
            logging.exception(f"Unable to clear {files_path} directories.")
            return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="smoke_test.py",
        description="Checks that bintars can run on bare bones distros.",
    )
    parser.add_argument("archive", help="Path to the binary tarball archive")
    parser.add_argument(
        "image_tests_file", help="Path to YAML file with a list of supported images"
    )
    parser.add_argument(
        "--docker_socket",
        default=None,
        help="Path to the docker daemon socket to start containers",
    )
    parser.add_argument(
        "--test_directory",
        default="./tests/",
        help="Where to extract the archive and run tests.",
    )
    parser.add_argument(
        "--container_name_prefix",
        default="smoke_test",
        help="Prefix for containers created during these tests. "
        "Name format is <prefix>_<uuid>. The script will clean up all"
        "container's whose names start with <prefix>",
    )
    args = parser.parse_args()

    setup_logging(logging.INFO)
    result = main(
        container_name_prefix=args.container_name_prefix,
        archive_path=Path(args.archive),
        tests_path=Path(args.test_directory),
        image_tests_file=args.image_tests_file,
        docker_socket=args.docker_socket,
    )
    sys.exit(result)
