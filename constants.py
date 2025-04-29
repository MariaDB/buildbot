import os

import yaml

DEVELOPMENT_BRANCH = "11.3"

# Used to trigger the appropriate main branch
BRANCHES_MAIN = [
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
    "12.0",
    "12.1",
    "12.2",
    "12.3",
    "main",
]

# Branches with special prefixes that invoke a BB run.
BB_TEST_BRANCHES = [
    "bb-*",
    "st-*",
    "prot-*",
    "refs/pull/*",
    "preview-1[0-9].*",
    "jpsn-*",
]

# A list of all branches that invoke a buildbot run.
ALL_BB_TEST_BRANCHES = BRANCHES_MAIN + BB_TEST_BRANCHES

STAGING_PROT_TEST_BRANCHES = [
    "prot-st-*",
]

# Defines what builders report status to GitHub
GITHUB_STATUS_BUILDERS = [
    "aarch64-macos-compile-only",
    "aarch64-debian-11",
    "amd64-debian-12",
    "amd64-debian-12-debug-embedded",
    "amd64-debian-12-deb-autobake",
    "amd64-debian-11-debug-ps-embedded",
    "amd64-debian-11-msan-clang-16",
    "amd64-fedora-40",
    "amd64-ubuntu-2004-debug",
    "amd64-ubuntu-2204-debug-ps",
    "amd64-windows",
]

# Special builders triggering
BUILDERS_BIG = ["amd64-ubuntu-2004-bigtest"]
BUILDERS_ECO = [
    "amd64-debian-10-eco-mysqljs",
    "amd64-debian-10-eco-pymysql",
    "amd64-ubuntu-2004-eco-php",
]

if os.environ["ENVIRON"] == "DEV":
    BUILDERS_WORDPRESS = ["amd64-rhel9-wordpress"]
    BUILDERS_DOCKERLIBRARY = ["amd64-rhel9-dockerlibrary"]
else:
    BUILDERS_WORDPRESS = ["amd64-rhel8-wordpress"]
    BUILDERS_DOCKERLIBRARY = ["amd64-rhel8-dockerlibrary"]

BUILDERS_GALERA_MTR = [
    "aarch64-debian-12",
    "s390x-ubuntu-2004",
    "s390x-ubuntu-2204",
    "ppc64le-ubuntu-2004",
    "ppc64le-ubuntu-2204",
    "amd64-freebsd-14",
]
BUILDERS_S3_MTR = [
    "aarch64-ubuntu-2004-debug",
    "amd64-ubuntu-2004-debug",
    "s390x-sles-1506",
]

# Defines branches for which we save packages
SAVED_PACKAGE_BRANCHES = BRANCHES_MAIN + [
    "bb-*-release",
    "bb-10.2-compatibility",
    "preview-*",
    "*pkgtest*",
]

# The trees for which we save binary packages.
RELEASE_BRANCHES = ["bb-*-release", "preview-*"]

# Note:
# Maximum supported branch is the one where the default distro MariaDB package major version <= branch
# For example, if Debian 10 has MariaDB 10.3 by default, we don't support MariaDB 10.2 on it.
SUPPORTED_PLATFORMS = {}
SUPPORTED_PLATFORMS["10.5"] = [
    "aarch64-centos-stream9",
    "aarch64-debian-11",
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
    "amd64-debian-11-msan-clang-16",
    "amd64-debian-12-asan-ubsan",
    "amd64-debian-12-rocksdb",
    "amd64-fedora-40-valgrind",
    "amd64-freebsd-14",
    "amd64-openeuler-2403",
    "amd64-rhel-7",
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
    "x86-debian-12-fulltest-debug",
]

SUPPORTED_PLATFORMS["10.6"] = SUPPORTED_PLATFORMS["10.5"].copy()

SUPPORTED_PLATFORMS["10.6"] += [
    "aarch64-ubuntu-2204",
    "amd64-msan-clang-20",
    "amd64-ubuntu-2204",
    "ppc64le-ubuntu-2204",
    "s390x-ubuntu-2204",
    "x86-debian-12",
]

SUPPORTED_PLATFORMS["10.9"] = SUPPORTED_PLATFORMS["10.6"].copy()

SUPPORTED_PLATFORMS["10.10"] = [
    "amd64-debian-11-aocc",
]
SUPPORTED_PLATFORMS["10.10"] += SUPPORTED_PLATFORMS["10.9"]

SUPPORTED_PLATFORMS["10.11"] = [
    "aarch64-centos-stream10",
    "aarch64-debian-12",
    "aarch64-fedora-40",
    "aarch64-fedora-41",
    "aarch64-ubuntu-2404",
    "amd64-centos-stream10",
    "amd64-debian-12",
    "amd64-debian-12-debug-embedded",
    "amd64-fedora-40",
    "amd64-fedora-41",
    "amd64-opensuse-1506",
    "amd64-sles-1506",
    "amd64-ubuntu-2404",
    "ppc64le-centos-stream10",
    "ppc64le-ubuntu-2404",
    "s390x-sles-1506",
    "s390x-ubuntu-2404",
    "ppc64le-debian-12",
]
SUPPORTED_PLATFORMS["10.11"] += SUPPORTED_PLATFORMS["10.10"]

SUPPORTED_PLATFORMS["11.0"] = SUPPORTED_PLATFORMS["10.11"].copy()
SUPPORTED_PLATFORMS["11.0"].remove("amd64-rhel-7")
SUPPORTED_PLATFORMS["11.1"] = SUPPORTED_PLATFORMS["11.0"].copy()
SUPPORTED_PLATFORMS["11.2"] = SUPPORTED_PLATFORMS["11.1"].copy()
SUPPORTED_PLATFORMS["11.3"] = SUPPORTED_PLATFORMS["11.2"].copy()
SUPPORTED_PLATFORMS["11.4"] = SUPPORTED_PLATFORMS["11.3"].copy()
SUPPORTED_PLATFORMS["11.4"] += [
    "aarch64-ubuntu-2410",
    "amd64-ubuntu-2410",
]

SUPPORTED_PLATFORMS["11.5"] = SUPPORTED_PLATFORMS["11.4"].copy()
SUPPORTED_PLATFORMS["11.5"].remove("amd64-centos-7-bintar")
SUPPORTED_PLATFORMS["11.6"] = SUPPORTED_PLATFORMS["11.5"].copy()
SUPPORTED_PLATFORMS["11.7"] = SUPPORTED_PLATFORMS["11.6"].copy()
SUPPORTED_PLATFORMS["11.7"] += ["amd64-almalinux-8-bintar"]
SUPPORTED_PLATFORMS["11.8"] = SUPPORTED_PLATFORMS["11.7"].copy()
SUPPORTED_PLATFORMS["11.8"] += [
    "aarch64-debian-sid",
    "amd64-debian-sid",
    "ppc64le-debian-sid",
    "x86-debian-sid",
]
SUPPORTED_PLATFORMS["12.0"] = SUPPORTED_PLATFORMS["11.8"].copy()
SUPPORTED_PLATFORMS["12.1"] = SUPPORTED_PLATFORMS["12.0"].copy()
SUPPORTED_PLATFORMS["12.2"] = SUPPORTED_PLATFORMS["12.1"].copy()
SUPPORTED_PLATFORMS["12.3"] = SUPPORTED_PLATFORMS["12.2"].copy()
SUPPORTED_PLATFORMS["main"] = SUPPORTED_PLATFORMS["12.3"].copy()

# Define environment variables for MTR step
MTR_ENV = {
    "MTR_PRINT_CORE": "detailed",
    "USER": "buildbot",
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
TEST_TYPE_TO_MTR_ARG = {
    "asan": "",
    "connect": "--suite=connect",
    "cursor": "--cursor-protocol",
    "debug": "",
    "debug-cursor": "--cursor-protocol",
    "debug-emb": "--embedded",
    "debug-emb-ps": "--embedded --ps-protocol",
    "debug-ps": "--ps-protocol",
    "debug-view": "--view-protocol",
    "emb": "--embedded",
    "emb-ps": "--embedded --ps-protocol",
    "msan": "",
    "nm": "",
    "nm_engines": "--suite=spider,spider/bg,engines/funcs,engines/iuds --big --mysqld=--open-files-limit=0 --mysqld=--log-warnings=1",
    "nm_func_1_2": "--suite=funcs_1,funcs_2,stress,jp --big --mysqld=--open-files-limit=0 --mysqld=--log-warnings=1",
    "optimizer_trace": "--suite=main --mysqld=--optimizer_trace=enabled=on",
    "ps": "--ps-protocol",
    "s3": "--suite=s3",
    "ubsan": "",
    "valgrind": "",
    "vault": "--suite=vault --big",
    "view": "--view-protocol",
}

# =============================================================================
# ============================ AUTO-GENERATED BELOW ===========================
# The following code is auto-generated based on the content of os_info.yaml.
# Edit with care

with open("/srv/buildbot/master/os_info.yaml") as f:
    OS_INFO = yaml.safe_load(f)

# Generate install builders based on the os_info data
BUILDERS_INSTALL = []
BUILDERS_UPGRADE = []
BUILDERS_AUTOBAKE = []
ALL_PLATFORMS = set()
for os_i in OS_INFO:
    for arch in OS_INFO[os_i]["arch"]:
        builder_name_autobake = (
            arch + "-" + os_i + "-" + OS_INFO[os_i]["type"] + "-autobake"
        )
        if not ("install_only" in OS_INFO[os_i] and OS_INFO[os_i]["install_only"]):
            ALL_PLATFORMS.add(arch)
            BUILDERS_AUTOBAKE.append(builder_name_autobake)
        # Currently there are no VMs for x86 and s390x
        if arch not in ["s390x", "x86"]:
            BUILDERS_INSTALL.append(builder_name_autobake + "-install")
            BUILDERS_UPGRADE.append(builder_name_autobake + "-minor-upgrade-all")
            BUILDERS_UPGRADE.append(
                builder_name_autobake + "-minor-upgrade-columnstore"
            )
            BUILDERS_UPGRADE.append(builder_name_autobake + "-major-upgrade")

BUILDERS_GALERA = list(
    map(lambda x: "gal-" + "-".join(x.split("-")[:3]), BUILDERS_AUTOBAKE)
)
