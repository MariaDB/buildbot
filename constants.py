import os

import yaml

DEVELOPMENT_BRANCH = "11.3"

# Used to trigger the appropriate main branch
branches_main = [
    "10.5",
    "10.6",
    "10.11",
    "11.0",
    "11.1",
    "11.2",
    "11.3",
    "11.4",
    "11.5",
    "11.6",
    "11.7",
    "11.8",
    "main",
]

# Defines what builders report status to GitHub
github_status_builders = [
    "aarch64-macos-compile-only",
    "amd64-debian-12",
    "amd64-debian-12-debug-embedded",
    "amd64-debian-12-deb-autobake",
    "amd64-debian-11-debug-ps-embedded",
    "amd64-debian-11-msan",
    "amd64-debian-11-msan-clang-16",
    "amd64-fedora-40",
    "amd64-last-N-failed",
    "amd64-ubuntu-2004-debug",
    "amd64-ubuntu-2204-debug-ps",
    "amd64-windows",
]

# Special builders triggering
builders_big = ["amd64-ubuntu-2004-bigtest"]
builders_eco = [
    "amd64-debian-10-eco-mysqljs",
    "amd64-debian-10-eco-pymysql",
    "amd64-ubuntu-2004-eco-php",
]

if os.getenv("ENVIRON") == "DEV":
    builders_wordpress = ["amd64-rhel9-wordpress"]
    builders_dockerlibrary = ["amd64-rhel9-dockerlibrary"]
else:
    builders_wordpress = ["amd64-rhel8-wordpress"]
    builders_dockerlibrary = ["amd64-rhel8-dockerlibrary"]

builders_galera_mtr = [
    "aarch64-debian-12",
    "amd64-fedora-39",
    "s390x-ubuntu-2004",
    "s390x-ubuntu-2204",
    "ppc64le-ubuntu-2004",
    "ppc64le-ubuntu-2204",
    "amd64-freebsd-14",
]
builders_s3_mtr = []

# Defines branches for which we save packages
savedPackageBranches = branches_main + [
    "bb-*-release",
    "bb-10.2-compatibility",
    "preview-*",
    "*pkgtest*",
]

# The trees for which we save binary packages.
releaseBranches = ["bb-*-release", "preview-*"]

# Note:
# Maximum supported branch is the one where the default distro MariaDB package major version <= branch
# For example, if Debian 10 has MariaDB 10.3 by default, we don't support MariaDB 10.2 on it.
supportedPlatforms = {}
supportedPlatforms["10.5"] = [
    "aarch64-centos-stream9",
    "aarch64-debian-10-bintar",
    "aarch64-debian-11",
    "aarch64-fedora-39",
    "aarch64-macos",
    "aarch64-macos-compile-only",
    "aarch64-openeuler-2403",
    "aarch64-rhel-8",
    "aarch64-rhel-9",
    "aarch64-ubuntu-2004",
    "aarch64-ubuntu-2004-debug",
    "amd64-centos-7-bintar",
    "amd64-centos-stream9",
    "amd64-debian-11",
    "amd64-debian-11-debug-ps-embedded",
    "amd64-debian-11-msan",
    "amd64-debian-11-msan-clang-16",
    "amd64-debian-12-asan-ubsan",
    "amd64-debian-12-rocksdb",
    "amd64-fedora-39",
    "amd64-fedora-40-valgrind",
    "amd64-freebsd-14",
    "amd64-openeuler-2403",
    "amd64-rhel-8",
    "amd64-rhel-9",
    "amd64-last-N-failed",
    "amd64-ubuntu-2004",
    "amd64-ubuntu-2004-debug",
    "amd64-ubuntu-2004-fulltest",
    "amd64-ubuntu-2204-debug-ps",
    "amd64-ubuntu-2204-icc",
    "amd64-ubuntu-2404-clang18-asan",
    "amd64-windows",
    "amd64-windows-packages",
    "ppc64be-aix-71",
    "ppc64le-centos-stream9",
    "ppc64le-rhel-8",
    "ppc64le-rhel-9",
    "ppc64le-ubuntu-2004",
    "ppc64le-ubuntu-2004-debug",
    "ppc64le-ubuntu-2004-without-server",
    "s390x-rhel-8",
    "s390x-rhel-9",
    "s390x-ubuntu-2004",
    "s390x-ubuntu-2004-debug",
    "x86-debian-12-fulltest",
]

supportedPlatforms["10.6"] = supportedPlatforms["10.5"].copy()

# Add only 10.5 supported platforms
supportedPlatforms["10.5"] += [
    "amd64-kvm-centos-6-bintar",
    "amd64-kvm-ubuntu-1604-bintar",
    "x86-kvm-centos-6-bintar",
    "x86-kvm-ubuntu-1604-bintar",
]

supportedPlatforms["10.6"] += [
    "aarch64-ubuntu-2204",
    "amd64-opensuse-1505",
    "amd64-sles-1505",
    "amd64-ubuntu-2204",
    "ppc64le-ubuntu-2204",
    "s390x-ubuntu-2204",
    "s390x-sles-1505",
    "x86-debian-12",
]

supportedPlatforms["10.9"] = supportedPlatforms["10.6"].copy()

supportedPlatforms["10.10"] = [
    "amd64-debian-11-aocc",
]
supportedPlatforms["10.10"] += supportedPlatforms["10.9"]

supportedPlatforms["10.11"] = [
    "aarch64-debian-12",
    "aarch64-fedora-40",
    "aarch64-fedora-41",
    "aarch64-ubuntu-2404",
    "amd64-debian-12",
    "amd64-debian-12-debug-embedded",
    "amd64-fedora-40",
    "amd64-fedora-41",
    "amd64-opensuse-1506",
    "amd64-sles-1506",
    "amd64-ubuntu-2404",
    "ppc64le-ubuntu-2404",
    "s390x-sles-1506",
    "s390x-ubuntu-2404",
    "ppc64le-debian-12",
]
supportedPlatforms["10.11"] += supportedPlatforms["10.10"]

supportedPlatforms["11.0"] = supportedPlatforms["10.11"].copy()
supportedPlatforms["11.1"] = supportedPlatforms["11.0"].copy()
supportedPlatforms["11.2"] = supportedPlatforms["11.1"].copy()
supportedPlatforms["11.3"] = supportedPlatforms["11.2"].copy()
supportedPlatforms["11.4"] = supportedPlatforms["11.3"].copy()
supportedPlatforms["11.4"] += [
    "aarch64-debian-sid",
    "aarch64-ubuntu-2410",
    "amd64-debian-sid",
    "amd64-ubuntu-2410",
    "ppc64le-debian-sid",
    "x86-debian-sid",
]
supportedPlatforms["11.5"] = supportedPlatforms["11.4"].copy()
supportedPlatforms["11.6"] = supportedPlatforms["11.5"].copy()
supportedPlatforms["11.7"] = supportedPlatforms["11.6"].copy()
supportedPlatforms["11.8"] = supportedPlatforms["11.7"].copy()
supportedPlatforms["main"] = supportedPlatforms["11.8"].copy()

# Define environment variables for MTR step
MTR_ENV = {
    "MTR_PRINT_CORE": "detailed",
}

# Define the mapping from MTR test types to mtr command line options
#
# * type names should be valid as file names
# * to avoid ambiguity, options in every line are sorted alphabetically,
#   that is emb-ps, not ps-emb
# * no test types for full, galera, xtra and big, because they don't matter
#   when a test is run by name as in `./mtr testname`
# * debug/asan/msan/ubsan tests need a type, because it's not enough to
#   run `./mtr testname`, they need a special build
test_type_to_mtr_arg = {
    "nm": "",
    "cursor": "--cursor-protocol",
    "ps": "--ps-protocol",
    "connect": "--suite=connect",
    "emb": "--embedded",
    "emb-ps": "--embedded --ps-protocol",
    "view": "--view-protocol",
    "asan": "",
    "msan": "",
    "ubsan": "",
    "valgrind": "",
    "debug": "",
    "debug-cursor": "--cursor-protocol",
    "debug-ps": "--ps-protocol",
    "debug-emb": "--embedded",
    "debug-emb-ps": "--embedded --ps-protocol",
    "debug-view": "--view-protocol",
    "nm_func_1_2": "--suite=funcs_1,funcs_2,stress,jp --big --mysqld=--open-files-limit=0 --mysqld=--log-warnings=1",
    "nm_engines": "--suite=spider,spider/bg,engines/funcs,engines/iuds --big --mysqld=--open-files-limit=0 --mysqld=--log-warnings=1",
}

# =============================================================================
# ============================ AUTO-GENERATED BELOW ===========================
# The following code is auto-generated based on the content of os_info.yaml.
# Edit with care

with open("/srv/buildbot/master/os_info.yaml") as f:
    os_info = yaml.safe_load(f)

# Generate install builders based on the os_info data
builders_install = []
builders_upgrade = []
builders_autobake = []
all_platforms = set()
for os_i in os_info:
    for arch in os_info[os_i]["arch"]:
        builder_name_autobake = (
            arch + "-" + os_i + "-" + os_info[os_i]["type"] + "-autobake"
        )
        if not ("install_only" in os_info[os_i] and os_info[os_i]["install_only"]):
            all_platforms.add(arch)
            builders_autobake.append(builder_name_autobake)
        # Currently there are no VMs for x86 and s390x and OpenSUSE and SLES
        if arch not in ["s390x", "x86"] and "sles" not in os_i:
            builders_install.append(builder_name_autobake + "-install")
            builders_upgrade.append(builder_name_autobake + "-minor-upgrade-all")
            builders_upgrade.append(
                builder_name_autobake + "-minor-upgrade-columnstore"
            )
            builders_upgrade.append(builder_name_autobake + "-major-upgrade")

builders_galera = list(
    map(lambda x: "gal-" + "-".join(x.split("-")[:3]), builders_autobake)
)
