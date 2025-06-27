from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class SRPMInstallBuildDeps(Command):
    """
    A command to install build dependencies from a source RPM (SRPM) file.
    """

    def __init__(
        self,
        workdir: PurePath = PurePath("."),
        dir_srpms: PurePath = PurePath("srpms"),
    ):
        super().__init__(name="Git", workdir=workdir)
        self.dir_srpms = dir_srpms

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
                # Configuration
                DIR_SRPMS="{str(self.dir_srpms)}"

                # Check SRPM directory
                if [[ ! -d "$DIR_SRPMS" ]]; then
                echo "Error: SRPM directory '$DIR_SRPMS' does not exist." >&2
                exit 1
                fi

                # Find exactly one .src.rpm
                shopt -s nullglob
                srpms=("$DIR_SRPMS"/*.src.rpm)
                shopt -u nullglob

                if [[ ${{#srpms[@]}} -eq 0 ]]; then
                echo "Error: No SRPM file found in '$DIR_SRPMS'." >&2
                exit 1
                elif [[ ${{#srpms[@]}} -gt 1 ]]; then
                echo "Error: More than one SRPM file found in '$DIR_SRPMS'. Only one is allowed." >&2
                printf 'Found:\n  %s\n' "${{#srpms[@]}}"
                exit 1
                fi

                srpm_file="${{#srpms[@]}}"
                source /etc/os-release
                # Run appropriate build dependency install command
                case "$ID" in
                fedora|centos)
                    echo "Installing build dependencies using dnf on $ID..."
                    sudo dnf --setopt=install_weak_deps=False builddep -y "$srpm_file"
                    ;;

                rhel)
                    major="${{VERSION_ID%%.*}}"
                    arch="$(uname -m)"
                    echo "Enabling CodeReady Builder repo for RHEL $major ($arch)..."
                    sudo dnf config-manager --enable "codeready-builder-for-rhel-${{major}}-${{arch}}-rpms"
                    echo "Installing build dependencies using dnf on RHEL..."
                    sudo dnf --setopt=install_weak_deps=False builddep -y "$srpm_file"
                    ;;

                "opensuse-leap"|"sles")
                    echo "Installing build dependencies using zypper on $ID..."
                    rpm -q --requires -p "$srpm_file" | xargs sudo zypper install -y -l
                    ;;

                *)
                    echo "Error: Unsupported distribution ID '$ID'." >&2
                    exit 1
                    ;;
                esac
            """,
        ]


class SRPMRebuild(Command):
    """
    A command to rebuild the RPM's from a source RPM.
    """

    def __init__(
        self,
        jobs: int,
        workdir: PurePath = PurePath("."),
        dir_srpms: PurePath = PurePath("srpms"),
    ):
        super().__init__(name="Git", workdir=workdir)
        self.dir_srpms = dir_srpms
        self.jobs = jobs

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
                # Configuration
                JOBS={self.jobs}                  # Execute on self.jobs cores
                DIR_SRPMS="{str(self.dir_srpms)}" # Directory containing one .src.rpm

                # Check for required tools
                for cmd in ccache rpmbuild; do
                if ! command -v "$cmd" &>/dev/null; then
                    echo "Error: '$cmd' is not installed or not in PATH." >&2
                    exit 1
                fi
                done

                # Check SRPM directory
                if [[ ! -d "$DIR_SRPMS" ]]; then
                echo "Error: SRPM directory '$DIR_SRPMS' does not exist." >&2
                exit 1
                fi

                # Find exactly one .src.rpm file
                shopt -s nullglob
                srpms=("$DIR_SRPMS"/*.src.rpm)
                shopt -u nullglob

                if [[ ${{#srpms[@]}} -eq 0 ]]; then
                echo "Error: No SRPM file found in '$DIR_SRPMS'." >&2
                exit 1
                elif [[ ${{#srpms[@]}} -gt 1 ]]; then
                echo "Error: More than one SRPM file found in '$DIR_SRPMS'. Only one is allowed." >&2
                printf 'Found:\n  %s\n' "${{srpms[@]}}"
                exit 1
                fi

                # Set parallel build flags
                echo "%_smp_mflags -j$JOBS" > "$HOME/.rpmmacros"

                # Use ccache for compilers
                export CC="ccache gcc"
                export CXX="ccache g++"

                # Rebuild SRPM
                echo "Rebuilding SRPM: ${{srpms[0]}} with -j$JOBS"
                rpmbuild --rebuild "${{srpms[0]}}"

                echo "SRPM rebuild completed successfully."
            """,
        ]


class SRPMCompare(Command):
    """
    A command to compare the RPMs from the CI and rebuilt directories.
    """

    def __init__(
        self,
        workdir: PurePath = PurePath("."),
        ci_rpms_dir: PurePath = PurePath("rpms"),
        rebuilt_rpms_dir: PurePath = PurePath("rpmbuild/RPMS"),
        exclude_rpms: str = "MariaDB-compat*",
    ):
        super().__init__(name="Git", workdir=workdir)
        self.ci_rpms_dir = ci_rpms_dir
        self.rebuilt_rpms_dir = rebuilt_rpms_dir
        self.exclude_rpms = exclude_rpms

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
                # Configuration
                DIR_CI={str(self.ci_rpms_dir)}
                DIR_REBUILT={str(self.rebuilt_rpms_dir)}
                EXCLUDE_PATTERNS=({self.exclude_rpms})
                REQUIRES_DIR="rpm_requires"  # directory to store rpm requires outputs

                # === Function: Validate directory existence and non-empty (simple ls check) ===
                validate_directory() {{
                    local DIR="$1"
                    if [ ! -d "$DIR" ]; then
                        echo "Error: Directory '$DIR' does not exist."
                        exit 1
                    fi

                    if [ -z "$(ls -A "$DIR" 2>/dev/null)" ]; then
                        echo "Error: Directory '$DIR' is empty."
                        exit 1
                    fi
                }}

                # === Function: Get filtered file list (with exclusions) ===
                get_filtered_file_list() {{
                    local DIR="$1"
                    local FIND_CMD=(find "$DIR" -maxdepth 1 -type f)

                    for PATTERN in "${{EXCLUDE_PATTERNS[@]}}"; do
                        FIND_CMD+=(! -name "$PATTERN")
                    done

                    "${{FIND_CMD[@]}}" | xargs -r -n1 basename | sort
                }}

                # === Function: Run rpm requires on each file in both directories and save outputs ===
                run_rpm_requires() {{
                    local FILES="$1"  # multiline string of filenames
                    mkdir -p "$REQUIRES_DIR/CI"
                    mkdir -p "$REQUIRES_DIR/REBUILT"

                    echo "Running rpm requires queries..."

                    while IFS= read -r FILENAME; do
                        local FILEPATH_CI="$DIR_CI/$FILENAME"
                        local FILEPATH_REBUILT="$DIR_REBUILT/$FILENAME"

                        rpm -q --requires -p "$FILEPATH_CI" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/CI/$FILENAME.requires"

                        rpm -q --requires -p "$FILEPATH_REBUILT" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/REBUILT/$FILENAME.requires"
                    done <<< "$FILES"
                }}

                # === Function: Compare rpm requires output files and report differences ===
                compare_requires() {{
                    local DIFFS_FOUND=0
                    echo "Comparing rpm requires files..."

                    for REQFILE_CI in "$REQUIRES_DIR/CI/"*.requires; do
                        FILENAME=$(basename "$REQFILE_CI" .requires)
                        REQFILE_REBUILT="$REQUIRES_DIR/REBUILT/$FILENAME.requires"

                        if [ ! -f "$REQFILE_REBUILT" ]; then
                            echo "File '$FILENAME' missing in REBUILT requires output."
                            DIFFS_FOUND=1
                            continue
                        fi

                        # Compare ignoring order and whitespace by sorting lines before diff
                        if ! diff -q <(sort "$REQFILE_CI") <(sort "$REQFILE_REBUILT") >/dev/null; then
                        echo "=================================================================="
                            echo "Difference found in requires for '$FILENAME':"
                        echo "=================================================================="
                            diff -u <(sort "$REQFILE_CI") <(sort "$REQFILE_REBUILT")
                            DIFFS_FOUND=1
                        fi
                    done

                    if [ $DIFFS_FOUND -eq 0 ]; then
                        echo "All rpm requires outputs match."
                    else
                        echo "Some differences detected in rpm requires outputs."
                        exit 1
                    fi
                }}

                # === Main script execution ===

                validate_directory "$DIR_CI"
                validate_directory "$DIR_REBUILT"

                FILES_CI=$(get_filtered_file_list "$DIR_CI")
                FILES_REBUILT=$(get_filtered_file_list "$DIR_REBUILT")

                ONLY_IN_CI=$(comm -23 <(echo "$FILES_CI") <(echo "$FILES_REBUILT"))
                ONLY_IN_REBUILT=$(comm -13 <(echo "$FILES_CI") <(echo "$FILES_REBUILT"))

                if [ -n "$ONLY_IN_CI" ] || [ -n "$ONLY_IN_REBUILT" ]; then
                    echo "Error: File name mismatch detected between directories."
                    if [ -n "$ONLY_IN_CI" ]; then
                        echo "Files only in CI ($DIR_CI):"
                        echo "$ONLY_IN_CI"
                    fi
                    if [ -n "$ONLY_IN_REBUILT" ]; then
                        echo "Files only in REBUILT ($DIR_REBUILT):"
                        echo "$ONLY_IN_REBUILT"
                    fi
                    exit 1
                else
                    echo "Success: Files match by name. Continuing processing..."

                    echo "$FILES_CI" > rpms_to_compare.txt

                    # Run rpm requires queries and save outputs with filtering
                    run_rpm_requires "$FILES_CI"

                    # Compare rpm requires outputs
                    compare_requires
                fi
            """,
        ]
