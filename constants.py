import yaml

DEVELOPMENT_BRANCH = "11.2"

# Used to trigger the appropriate main branch
branches_main = [
        '10.4',
        '10.5',
        '10.6',
        '10.8',
        '10.10',
        '10.11',
        '11.0',
        '11.1',
        '11.2',
        ]

# Defines what builders report status to GitHub
github_status_builders = [
        "amd64-centos-7",
        "amd64-centos-7-rpm-autobake",
        "amd64-debian-10",
        "amd64-debian-10-debug-embedded",
        "amd64-debian-10-deb-autobake",
        "amd64-debian-11-debug-ps-embedded",
        "amd64-debian-11-msan",
        "amd64-fedora-38",
        "amd64-ubuntu-2004-debug",
        "amd64-ubuntu-2204-debug-ps",
        "amd64-windows",
        ]

# Special builders triggering
builders_big = ["amd64-ubuntu-2004-bigtest"]
builders_dockerlibrary = ["amd64-rhel8-dockerlibrary"]
builders_eco = [
        "amd64-debian-10-eco-mysqljs",
        "amd64-debian-10-eco-pymysql",
        "amd64-ubuntu-2004-eco-dbdeployer",
        "amd64-ubuntu-2004-eco-php",
        ]
builders_wordpress = ["amd64-rhel8-wordpress"]
builders_galera_mtr = [
        "aarch64-debian-12",
        "amd64-fedora-37",
        "amd64-ubuntu-2304",
        ]

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
supportedPlatforms["10.4"] = [
        'aarch64-centos-stream8',
        'aarch64-debian-10',
        'aarch64-debian-10-bintar',
        'aarch64-rhel-8',
        'aarch64-ubuntu-2004',
        'aarch64-ubuntu-2004-debug',
        'amd64-centos-7',
        'amd64-centos-7-bintar',
        'amd64-centos-stream8',
        'amd64-debian-10',
        'amd64-debian-10-debug-embedded',
        'amd64-debian-11-debug-ps-embedded',
        'amd64-opensuse-15',
        'amd64-rhel-7',
        'amd64-rhel-8',
        'amd64-ubuntu-1804-clang10-asan',
        'amd64-ubuntu-2004',
        'amd64-ubuntu-2004-debug',
        'amd64-ubuntu-2004-fulltest',
        'amd64-ubuntu-2204-debug-ps',
        'amd64-ubuntu-2204-valgrind',
        'amd64-windows',
        'amd64-windows-packages',
        'ppc64le-centos-stream8',
        'ppc64le-rhel-8',
        'ppc64le-ubuntu-2004',
        'ppc64le-ubuntu-2004-debug',
        'ppc64le-ubuntu-2004-without-server',
        ]

supportedPlatforms["10.5"] = [
        'aarch64-centos-stream9',
        'aarch64-debian-11',
        'aarch64-fedora-37',
        'aarch64-fedora-38',
        'aarch64-rhel-9',
        'aix',
        'amd64-centos-stream9',
        'amd64-debian-11',
        'amd64-debian-11-msan',
        'amd64-fedora-37',
        'amd64-fedora-38',
        'amd64-rhel-9',
        'ppc64le-centos-stream9',
        'ppc64le-debian-11',
        'ppc64le-rhel-9',
        's390x-rhel-8',
        's390x-rhel-9',
        's390x-sles-12',
        's390x-sles-15',
        's390x-ubuntu-2004',
        ]
supportedPlatforms["10.5"] += supportedPlatforms["10.4"]

supportedPlatforms["10.6"] = [
        'aarch64-ubuntu-2204',
        'aarch64-ubuntu-2210',
        'amd64-ubuntu-2204',
        'amd64-ubuntu-2210',
        'ppc64le-ubuntu-2204',
        's390x-ubuntu-2204',
        ]
supportedPlatforms["10.6"] += supportedPlatforms["10.5"]

supportedPlatforms["10.9"] = supportedPlatforms["10.6"].copy()

supportedPlatforms["10.10"] = [
        'amd64-debian-11-aocc',
        ]
supportedPlatforms["10.10"] += supportedPlatforms["10.9"]

supportedPlatforms["10.11"] = [
        'aarch64-debian-12',
        'aarch64-debian-sid',
        'aarch64-ubuntu-2304',
        'aarch64-ubuntu-2310',
        'amd64-debian-12',
        'amd64-debian-sid',
        'amd64-ubuntu-2304',
        'amd64-ubuntu-2310',
        'ppc64le-debian-sid',
        'x86-debian-sid',
        'ppc64le-debian-12',
        ]
supportedPlatforms["10.11"] += supportedPlatforms["10.10"]

supportedPlatforms["11.0"] = supportedPlatforms["10.11"].copy()
supportedPlatforms["11.1"] = supportedPlatforms["11.0"].copy()
supportedPlatforms["11.2"] = supportedPlatforms["11.1"].copy()

# Define environment variables for MTR step
MTR_ENV = {
    'MTR_PRINT_CORE': 'detailed',
    }

# =============================================================================
# ============================ AUTO-GENERATED BELOW ===========================
# The following code is auto-generated based on the content of os_info.yaml.
# Edit with care

with open('/srv/buildbot/master/os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

# Generate install builders based on the os_info data
builders_install = []
builders_upgrade = []
builders_autobake = []
all_platforms = set()
for os_i in os_info:
    for arch in os_info[os_i]['arch']:
        all_platforms.add(arch)
        builder_name_autobake = arch + '-' + os_i + '-' + os_info[os_i]['type'] + '-autobake'
        builders_autobake.append(builder_name_autobake)
        # Currently there are no VMs for x86 and s390x and OpenSUSE and SLES
        addInstall = True
        if 'has_install' in os_info[os_i]:
            addInstall = os_info[os_i]['has_install']
        if arch not in ['s390x', 'x86'] and addInstall:
            builders_install.append(builder_name_autobake + '-install')
            builders_upgrade.append(builder_name_autobake + '-minor-upgrade')
            builders_upgrade.append(builder_name_autobake + '-major-upgrade')

builders_galera = list(map(lambda x: "gal-" + "-".join(x.split('-')[:3]), builders_autobake))

