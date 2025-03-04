#!/bin/bash

set -eu

if [ $# -ne 4 ]; then
    echo "Usage: $0 <ci_base_url> <tarball_number> <autobake_builder> <<no_of_jobs>>"
    echo "Example: $0 https://ci.mariadb.org 54438 amd64-fedora-39-rpm-autobake 7"
    exit 1
fi

ci_base_url=$1
tarball_number=$2
autobake_builder=$3
jobs=$4
base_url="$ci_base_url/$tarball_number/$autobake_builder"

# Create the rpms and srpms directories if they don't exist
mkdir -p rpms srpms

# Download RPMS / SRPMS from CI
echo "Downloading RPM files to 'rpms/' directory..."
wget -r -l1 -H -nd -A "*.rpm" "$base_url/rpms/" -P rpms/

echo "Downloading SRPM files to 'srpms/' directory..."
wget -r -l1 -H -nd -A "*.rpm" "$base_url/srpms/" -P srpms/

# Load OS related information
source /etc/os-release

# MariaDB-compat cannot be built from srpm, so remove it and all
# dependencies on it.
rm -fv rpms/MariaDB-compat-*rpm

# There's no libjudy in sles123 repositories
# and judy-devel in sles 15.3 repositories
case $ID in
  "sles")
    rm -fv rpms/*-oqgraph-*rpm;
    ;;
esac

# Install build dependencies
# SUSE doesn't have $PLATFORM_ID
case ${PLATFORM_ID:-NO_PLATFORM_ID} in
    "platform:el8"|"platform:el9"|"platform:f39"|"platform:f40"|"platform:f41")
        case $ID in \
            "rhel") \
                # shellcheck disable=SC2086,SC2046
                sudo dnf config-manager --enable codeready-builder-for-rhel-${VERSION%%.*}-$(uname -m)-rpms; \
                ;; \
        esac; \
        sudo dnf --setopt=install_weak_deps=False builddep -y srpms/*.src.rpm; \
        ;; \
    *)
        case $ID in \
            "opensuse-leap"|"sles") \
                rpm -q --requires -p srpms/*.src.rpm | xargs sudo zypper install -y -l \
                ;; \
        *)
            echo "Unknown platform: $ID";
            exit 1; \
            ;; \
        esac; \
        ;; \
esac

# Rebuild from SRPMs
echo -e "\nRebuilding the RPM's..."
# Set the number of jobs (for make)
echo "%_smp_mflags -j$jobs" > ~/.rpmmacros
rpmbuild --rebuild srpms/*.src.rpm

echo -e "\nPerforming RPM dependency checks..."

echo "Extract dependencies from CI RPM's..."
echo rpms/*.rpm | xargs -n1 rpm -q --requires -p | \
    sed -e 's/>=.*/>=/; s/\([A-Z0-9._]*\)\([0-9]*bit\)$//; /MariaDB-compat/d; /rpmlib(FileCaps)/d' | \
    sort -u > requires-ci.txt

echo "Extract dependencies from rebuilt RPM's..."
echo ~/rpmbuild/RPMS/*.rpm | xargs -n1 rpm -q --requires -p | \
    sed -e 's/>=.*/>=/; s/\([A-Z0-9._]*\)\([0-9]*bit\)$//; /rpmlib(FileCaps)/d' | \
    sort -u > requires-rebuilt.txt

# Compare the dependencies of the original and rebuilt RPMs
echo -e "\nComparing dependencies..."
diff -u requires-*.txt

echo -e "\nAll tasks completed successfully!"
