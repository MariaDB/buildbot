import argparse
import logging
import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Generator, Iterable, Tuple

import magic
import yaml
from common import prepare_test_directory, run_command, setup_logging


def check_file_is_elf_binary_callback(file_path: str) -> str | None:
    global mime
    try:
        file_type = mime.from_file(file_path)
        if "elf" in file_type.lower():  # Identify ELF files
            return file_path
    except Exception as e:
        logging.error(f"Error checking file {file_path}: {e}")
    return None


def start_worker():
    global mime
    mime = magic.Magic()


def get_file_paths(path: str) -> Generator[str, None, None]:
    # Generator to feed file paths to processes.
    for root, _, files in os.walk(path):
        for file in files:
            yield os.path.join(root, file)


def get_executables(path: str):
    """
    Recursively searches for ELF executable files and libraries in the given
    path using a multiprocess approach (to speed up).

    Args:
        path (str): Root directory to search.

    Returns:
        list: List of paths to ELF executables and libraries.
    """
    executables = []

    # Use ProcessPoolExecutor to process files in parallel
    # This offers a 10x speed up compared to single threaded.
    with ProcessPoolExecutor(
        initializer=start_worker, max_workers=os.cpu_count()
    ) as executor:
        results = executor.map(check_file_is_elf_binary_callback, get_file_paths(path))

    # Collect non-None results
    executables = [result for result in results if result]

    return executables


def get_file_dependencies_callback(file: str) -> Tuple[str, set[str]]:
    result = set()
    output = run_command(f"readelf -d {file}")
    if output is None:
        logging.error(f"Failed to check libraries for {file}.")
        return file, False

    pattern = "Shared library: \\[(\\S*)\\]"
    regex_shared_library = re.compile(pattern)

    for line in output.splitlines():
        # Here is an example line we match:
        # 0x0000000000000001 (NEEDED)      Shared library: [libsystemd.so.0]

        match = regex_shared_library.search(line)
        if not match:
            continue
        library = match.group(1)
        result.add(library)

    return file, result


def get_dependencies_for_files(files: Iterable[str]) -> dict[str, list[str]]:
    with ProcessPoolExecutor(
        initializer=start_worker, max_workers=os.cpu_count()
    ) as executor:
        results = executor.map(get_file_dependencies_callback, files)

    deps = {}
    for full_file_path, file_deps in results:
        # TODO(cvicentiu) Perhaps this should be marked as a failure.
        # Unable to read file dependencies, skip the file.
        if file_deps is False:
            continue

        deps[full_file_path] = file_deps

    return deps


def remove_base_path_from_files(
    dependencies: dict[str, list[str]], base_path: str
) -> dict[str, list[str]]:
    """
    For all keys in dependencies, remove the base_path prefix.
    "./tests/mariadb-11.6.2-linux-systemd-x86_64/lib/libgalera_smm.so"
    becomes
    "lib/libgalera_smm.so"
    """
    result = {}
    for full_file_name, deps in dependencies.items():
        # If this assert fails, there is a bug in the testing script.
        assert full_file_name.startswith(base_path)
        file_name = full_file_name[len(base_path) + 1 :]
        result[file_name] = deps
    return result


def dependencies_to_canonical_repr(
    dependencies: dict[str, set[str]], version: str, base_path: Path
) -> dict[str, dict[str, list[str]]]:
    dependencies = remove_base_path_from_files(dependencies, base_path.as_posix())
    result = {
        "version": version,
        "files": {},
    }

    for file, deps in dependencies.items():
        result["files"][file] = list(sorted(deps))

    return result


def get_standard_dependencies(path: str):
    with open(path, "r") as spec_file:
        return yaml.safe_load(spec_file)


def get_executable_files_dependencies(path: str):
    files = get_executables(path)
    return get_dependencies_for_files(files)


def compare_versions(archive_deps, standard_deps, allow_cross_version: bool):
    a_version = archive_deps["version"]
    s_version = standard_deps["version"]

    if a_version != s_version:
        if allow_cross_version:
            logging.warn(f"WARNING: version mismatch {a_version} {s_version}")
        else:
            logging.error(f"version mismatch {a_version} {s_version}")
            return True
    return False


def compare_dependencies(archive_deps, standard_deps):
    error = False
    files = archive_deps["files"]
    control = standard_deps["files"]

    files_set = set(files.keys())
    control_set = set(control.keys())

    files_extra = files_set.difference(control_set)
    files_missing = control_set.difference(files_set)
    common = files_set.intersection(control_set)

    if files_extra:
        logging.error(f"We have extra files! {files_extra}")
        error = True

    if files_missing:
        logging.error(f"We have missing files from the archive! {files_missing}")
        error = True

    for file in common:
        deps_extra = set(files[file]).difference(control[file])
        deps_missing = set(control[file]).difference(files[file])

        if deps_extra:
            logging.error(f"We have extra deps for {file}! {deps_extra}")
            error = True
        if deps_missing:
            logging.error(f"We have missing deps for {file}! {deps_missing}")
            error = True

    return error


def main(
    archive_path: Path,
    tests_path: Path,
    deps_file: Path,
    record: bool,
    allow_cross_version: bool,
) -> int:
    files_path = None
    try:
        # Unpack the archive
        files_path, major_minor = prepare_test_directory(archive_path, tests_path)

        logging.info("Fetching archive dependencies")
        dependencies = get_executable_files_dependencies(files_path)

        canonical_deps = dependencies_to_canonical_repr(
            dependencies, version=major_minor, base_path=files_path
        )

        if record:
            logging.info(f"Recording new result to {deps_file}")
            with open(deps_file, "w") as f:
                yaml.dump(canonical_deps, f, indent=4)
            return 0

        # Validate dependencies.
        standard = get_standard_dependencies(deps_file)

        error = False  # track any errors so we can return properly.
        error |= compare_versions(canonical_deps, standard, allow_cross_version)
        error |= compare_dependencies(canonical_deps, standard)

        if error:
            logging.error("Some tests failed")
            return 1
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

    logging.info("All OK")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="deps_test.py", description="Checks/Records bintar files and dependencies"
    )
    parser.add_argument("archive", help="Path to the binary tarball archive")
    parser.add_argument(
        "deps_file", help="Path to YAML file with a list of dependencies"
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Use the bintar archive to generate a deps file",
    )
    parser.add_argument(
        "--test_directory",
        type=str,
        default="./tests/",
        help="Where to extract the archive and run tests.",
    )
    parser.add_argument(
        "--allow_cross_version",
        action="store_true",
        help="Tests pass even if there is a "
        "version mismatch between the archive and "
        "the deps_file version",
    )
    args = parser.parse_args()

    setup_logging(logging.INFO)
    result = main(
        archive_path=Path(args.archive),
        tests_path=Path(args.test_directory),
        deps_file=Path(args.deps_file),
        record=args.record,
        allow_cross_version=args.allow_cross_version,
    )
    sys.exit(result)
