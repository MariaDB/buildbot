#!/bin/bash

# Configuration
DIR_SRPMS=$1             # Directory containing one .src.rpm
JOBS=$2                  # Execute on self.jobs cores

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

if [[ ${#srpms[@]} -eq 0 ]]; then
    echo "Error: No SRPM file found in '$DIR_SRPMS'." >&2
    exit 1
elif [[ ${#srpms[@]} -gt 1 ]]; then
    echo "Error: More than one SRPM file found in '$DIR_SRPMS'. Only one is allowed." >&2
    printf 'Found:\n  %s\n' "${srpms[@]}"
    exit 1
fi

# Set parallel build flags
echo "%_smp_mflags -j$JOBS" > "$HOME/.rpmmacros"

# Use ccache for compilers
export CMAKE_C_COMPILER_LAUNCHER="ccache"
export CMAKE_CXX_COMPILER_LAUNCHER="ccache"

# Rebuild SRPM
srpm_file="${srpms[0]}"
echo "Rebuilding SRPM: $srpm_file with -j$JOBS"
rpmbuild --rebuild "$srpm_file"

echo "SRPM rebuild completed successfully."