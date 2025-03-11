import logging
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Tuple

# ANSI escape codes for colors
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"


def setup_logging(level: int):
    # Custom log formatter to include colors
    class ColoredFormatter(logging.Formatter):
        def format(self, record):
            if record.levelno == logging.INFO:
                color = GREEN
            elif record.levelno == logging.ERROR:
                color = RED
            elif record.levelno == logging.WARNING:
                color = YELLOW
            else:
                color = RESET

            # Apply color to the message
            record.msg = f"{color}{record.levelname}{RESET}: {record.msg}"
            return super().format(record)

    # Basic logging configuration
    logging.basicConfig(
        level=level,
        format="%(message)s",  # No logger name or timestamp
        handlers=[logging.StreamHandler()],
    )

    # Apply the custom formatter
    logging.getLogger().handlers[0].setFormatter(ColoredFormatter("%(message)s"))


# Helper functions
def run_command(command):
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running command '{command}': {e} {e.stderr.strip()}")
        return None


def _unpack_archive(tarball_path: Path, dst_path: Path):
    logging.info(f"Extracting archive {tarball_path}")
    with tarfile.open(str(tarball_path), "r:*") as tar:
        tar.extractall(path=str(dst_path), filter="fully_trusted")


def _parse_archive_path(archive_path: Path) -> Tuple[str, str]:
    archive_name = archive_path.name

    # Removes the last extension (e.g., .gz)
    base_name = Path(archive_name).stem
    # Check and remove the .tar extension
    if base_name.endswith(".tar"):
        base_name = Path(base_name).stem

    # Let's extract the product version from the archive:
    match = re.search("([1-9][0-9]+\\.[0-9]+\\.[0-9]+)", base_name)
    if not match:
        logging.error(f"Archive name {archive_name} must contain product version")
        sys.exit(1)

    # Only interested in major and minor version numbers, not point.
    version = match.group(0).split(".")
    major_minor = f"{version[0]}.{version[1]}"

    logging.info(f"Product version (major.minor) {major_minor}")

    return base_name, major_minor


def prepare_test_directory(archive_path: Path, tests_path: Path) -> Tuple[Path, str]:
    base_name, major_minor = _parse_archive_path(archive_path)
    # The archive contains a folder with the same name as the archive.
    # We are interested in the contents within that folder, as that's where
    # the files are.
    files_path = tests_path / base_name

    # Cleanup any previous run.
    shutil.rmtree(files_path, ignore_errors=True)

    # Create the test directory.
    tests_path.mkdir(parents=True, exist_ok=True)

    _unpack_archive(archive_path, tests_path)

    # Sanity check that the archive has maintained its format.
    assert files_path.is_dir()

    return files_path, major_minor
