#!/bin/bash

# Configuration
DIR_SRPMS=$1

# Check SRPM directory
if [[ ! -d "$DIR_SRPMS" ]]; then
    echo "Error: SRPM directory '$DIR_SRPMS' does not exist." >&2
    exit 1
fi

# Find exactly one .src.rpm
shopt -s nullglob
srpms=("$DIR_SRPMS"/*.src.rpm)
shopt -u nullglob

if [[ ${#srpms[@]} -eq 0 ]]; then
    echo "Error: No SRPM file found in '$DIR_SRPMS'." >&2
    exit 1
elif [[ ${#srpms[@]} -gt 1 ]]; then
    echo "Error: More than one SRPM file found in '$DIR_SRPMS'. Only one is allowed." >&2
    printf 'Found:\n  %s\n' "${#srpms[@]}"
    exit 1
fi

srpm_file="${srpms[0]}"

# Run appropriate build dependency install command
source /etc/os-release
case "$ID" in
    rhel)
        major="${VERSION_ID%%.*}"
        arch="$(uname -m)"
        echo "Enabling CodeReady Builder repo for RHEL $major ($arch)..."
        sudo dnf config-manager --enable "codeready-builder-for-rhel-${major}-${arch}-rpms"
        ;&
    fedora|centos)
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