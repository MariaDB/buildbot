import yaml

DEVELOPMENT_BRANCH = "11.0"

# Used to trigger the appropriate main branch
branches_main = [
        '10.3',
        '10.4',
        '10.5',
        '10.6',
        '10.7',
        '10.8',
        '10.9',
        '10.10',
        '10.11',
        '11.0',
        ]

# Defines what builders report status to GitHub
github_status_builders = [
        "amd64-centos-7",
        "amd64-centos-7-rpm-autobake",
        "amd64-debian-10",
        "amd64-debian-10-debug-embedded",
        "amd64-debian-10-deb-autobake",
        "amd64-debian-11-debug-ps-embedded",
        "amd64-fedora-36",
        "amd64-ubuntu-2004-clang11",
        "amd64-ubuntu-2004-debug",
        "amd64-ubuntu-2204-debug-ps",
        "amd64-windows",
        ]

# Special builders triggering
builders_big = ["amd64-ubuntu-1804-bigtest"]
builders_dockerlibrary = ["amd64-rhel8-dockerlibrary"]
builders_eco = [
        "amd64-debian-10-eco-mysqljs",
        "amd64-debian-10-eco-pymysql",
        "amd64-ubuntu-2004-eco-dbdeployer",
        "amd64-ubuntu-2004-eco-php",
        ]
builders_wordpress = ["amd64-rhel8-wordpress"]

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
supportedPlatforms["10.3"] = [
        'aarch64-centos-stream8',
        'aarch64-debian-10',
        'aarch64-rhel-8',
        'aarch64-ubuntu-1804',
        'aarch64-ubuntu-2004',
        'aarch64-ubuntu-2004-debug',
        'amd64-centos-7',
        'amd64-centos-stream8',
        'amd64-debian-10',
        'amd64-debian-10-debug-embedded',
        'amd64-debian-11-debug-ps-embedded',
        'amd64-opensuse-15',
        'amd64-rhel-7',
        'amd64-rhel-8',
        'amd64-ubuntu-1804',
        'amd64-ubuntu-1804-clang10',
        'amd64-ubuntu-1804-clang10-asan',
        'amd64-ubuntu-1804-clang6',
        'amd64-ubuntu-2004',
        'amd64-ubuntu-2004-clang11',
        'amd64-ubuntu-2004-debug',
        'amd64-ubuntu-2204-debug-ps',
        'amd64-ubuntu-2204-valgrind',
        'amd64-windows',
        'amd64-windows-packages',
        'ppc64le-centos-stream8',
        'ppc64le-rhel-8',
        'ppc64le-ubuntu-1804',
        'ppc64le-ubuntu-1804-without-server',
        'ppc64le-ubuntu-2004',
        'ppc64le-ubuntu-2004-clang1x',
        'ppc64le-ubuntu-2004-debug',
        ]

supportedPlatforms["10.4"] = supportedPlatforms["10.3"]

supportedPlatforms["10.5"] = [
        'aarch64-debian-11',
        'aarch64-fedora-36',
        'aarch64-fedora-37',
        'aarch64-rhel-9',
        'aix',
        'amd64-debian-11',
        'amd64-fedora-36',
        'amd64-fedora-37',
        'amd64-rhel-9',
        'amd64-ubuntu-2004-msan',
        'ppc64le-debian-11',
        'ppc64le-rhel-9',
        's390x-rhel-8',
        's390x-rhel-9',
        's390x-sles-12',
        's390x-sles-15',
        's390x-ubuntu-2004',
        'x86-debian-sid',
        ]
supportedPlatforms["10.5"] += supportedPlatforms["10.4"]

supportedPlatforms["10.6"] = [
        'aarch64-debian-sid',
        'aarch64-ubuntu-2204',
        'aarch64-ubuntu-2210',
        'amd64-debian-sid',
        'amd64-ubuntu-2004-fulltest',
        'amd64-ubuntu-2204',
        'amd64-ubuntu-2210',
        'ppc64le-debian-sid',
        'ppc64le-ubuntu-2204',
        's390x-ubuntu-2204',
        ]
supportedPlatforms["10.6"] += supportedPlatforms["10.5"]

supportedPlatforms["10.7"] = supportedPlatforms["10.6"]
supportedPlatforms["10.8"] = supportedPlatforms["10.7"]
supportedPlatforms["10.9"] = supportedPlatforms["10.8"]

supportedPlatforms["10.10"] = [
        'amd64-debian-11-aocc',
        ]
supportedPlatforms["10.10"] += supportedPlatforms["10.9"]

supportedPlatforms["10.11"] = supportedPlatforms["10.10"]
supportedPlatforms["10.11"] += [
        'aarch64-ubuntu-2304',
        'amd64-ubuntu-2304',
        ]
supportedPlatforms["11.0"] = supportedPlatforms["10.11"]

# Define environment variables for MTR step
MTR_ENV = {
    'MTR_PRINT_CORE': 'detailed',
    }

# Hack to remove all github_status_builders since they are triggered separately
for k in supportedPlatforms:
    supportedPlatforms[k] = list(filter(lambda x: x not in github_status_builders, supportedPlatforms[k]))

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
for os in os_info:
    for arch in os_info[os]['arch']:
        all_platforms.add(arch)
        builder_name_autobake = arch + '-' + os + '-' + os_info[os]['type'] + '-autobake'
        builders_autobake.append(builder_name_autobake)
        # Currently there are no VMs for x86 and s390x and OpenSUSE and SLES
        addInstall = True
        if 'has_install' in os_info[os]:
            addInstall = os_info[os]['has_install']
        if arch not in ['s390x', 'x86'] and addInstall:
            builders_install.append(builder_name_autobake + '-install')
            builders_upgrade.append(builder_name_autobake + '-minor-upgrade')
            builders_upgrade.append(builder_name_autobake + '-major-upgrade')

builders_galera = list(map(lambda x: "gal-" + "-".join(x.split('-')[:3]), builders_autobake))

