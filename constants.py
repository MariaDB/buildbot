import yaml

with open('/srv/buildbot/master/os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

branches_main=['10.3', '10.4', '10.5', '10.6', '10.7', '10.8', '10.9', '10.10', '10.11']

github_status_builders = [
        "amd64-centos-7",
        "amd64-debian-10",
        "amd64-fedora-35",
        "amd64-ubuntu-2004-clang11",
        "amd64-ubuntu-2004-debug",
        "amd64-windows",
        ]

release_builders = [
        "aarch64-centos-stream8-rpm-autobake",
        "aarch64-debian-10",
        "aarch64-debian-10-deb-autobake",
        "aarch64-debian-11",
        "aarch64-debian-11-deb-autobake",
        "aarch64-debian-sid",
        "aarch64-debian-sid-deb-autobake",
        "aarch64-fedora-35",
        "aarch64-fedora-35-rpm-autobake",
        "aarch64-fedora-36",
        "aarch64-fedora-36-rpm-autobake",
        "aarch64-rhel-8",
        "aarch64-rhel-8-rpm-autobake",
        "aarch64-rhel-9",
        "aarch64-rhel-9-rpm-autobake",
        "aarch64-ubuntu-1804",
        "aarch64-ubuntu-1804-deb-autobake",
        "aarch64-ubuntu-2004",
        "aarch64-ubuntu-2004-deb-autobake",
        "amd64-centos-stream8-rpm-autobake",
        "amd64-debian-sid",
        "amd64-debian-sid-deb-autobake",
        "amd64-ubuntu-2004",
        "amd64-ubuntu-2004-deb-autobake",
        "ppc64le-centos-stream8-rpm-autobake",
        "ppc64le-debian-11",
        "ppc64le-debian-11-deb-autobake",
        "ppc64le-debian-sid",
        "ppc64le-debian-sid-deb-autobake",
        "s390x-ubuntu-2004",
        "s390x-ubuntu-2004-deb-autobake",
        "s390x-ubuntu-2204",
        "s390x-ubuntu-2204-deb-autobake",
        "s390x-rhel-8",
        "s390x-rhel-8-rpm-autobake",
        "s390x-rhel-9",
        "s390x-rhel-9-rpm-autobake",
        "s390x-sles-15",
        "s390x-sles-15-rpm-autobake",
        ]

builders_big=["amd64-ubuntu-1804-bigtest"]

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
        if arch not in ['s390x', 'x86'] and os not in ['opensuse-15', 'sles-12', 'sles-15']:
            builders_install.append(builder_name_autobake + '-install')
            builders_upgrade.append(builder_name_autobake + '-minor-upgrade')
            builders_upgrade.append(builder_name_autobake + '-major-upgrade')

builders_galera = list(map(lambda x: "gal-" + "-".join(x.split('-')[:3]), builders_autobake))

builders_eco=["amd64-ubuntu-2004-eco-php", "amd64-debian-10-eco-pymysql", "amd64-debian-10-eco-mysqljs", "amd64-ubuntu-2004-eco-dbdeployer"]

builders_dockerlibrary=["amd64-rhel8-dockerlibrary"]

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
        'amd64-centos-7',
        'amd64-centos-stream8',
        'amd64-debian-10',
        'amd64-opensuse-15',
        'amd64-rhel-7',
        'amd64-rhel-8',
        'amd64-ubuntu-1804',
        'amd64-ubuntu-1804-clang10',
        'amd64-ubuntu-1804-clang10-asan',
        'amd64-ubuntu-1804-clang6',
        'amd64-ubuntu-2004-debug',
        'amd64-ubuntu-1804-valgrind',
        'amd64-ubuntu-2004',
        'amd64-ubuntu-2004-clang11',
        'amd64-windows',
        'ppc64le-centos-stream8',
        'ppc64le-rhel-8',
        'ppc64le-ubuntu-1804',
        'ppc64le-ubuntu-2004-clang1x',
        'ppc64le-ubuntu-1804-without-server',
        'ppc64le-ubuntu-2004']

supportedPlatforms["10.4"] = supportedPlatforms["10.3"]

supportedPlatforms["10.5"] = [
        'aarch64-debian-11',
        'aarch64-rhel-9',
        'aix',
        'amd64-debian-11',
        'amd64-rhel-9',
        'ppc64le-debian-11',
        'ppc64le-rhel-9',
        's390x-ubuntu-2004',
        's390x-rhel-8',
        's390x-rhel-9',
        's390x-sles-15']
supportedPlatforms["10.5"].append(supportedPlatforms["10.4"])

supportedPlatforms["10.6"] = [
        'aarch64-debian-sid',
        'aarch64-ubuntu-2204',
        'amd64-debian-sid',
        'amd64-ubuntu-2004-fulltest',
        'amd64-ubuntu-2204',
        'ppc64le-debian-sid',
        'ppc64le-ubuntu-2204',
        's390x-ubuntu-2204',
        ]
supportedPlatforms["10.6"].append(supportedPlatforms["10.6"])

supportedPlatforms["10.7"] = supportedPlatforms["10.6"]
supportedPlatforms["10.8"] = supportedPlatforms["10.7"]
supportedPlatforms["10.9"] = supportedPlatforms["10.8"]
supportedPlatforms["10.10"] = supportedPlatforms["10.9"]
supportedPlatforms["10.11"] = supportedPlatforms["10.10"]

# Hack to remove all github_status_builders since they are triggered separately
for k in supportedPlatforms:
    supportedPlatforms[k] = list(filter(lambda x: x not in github_status_builders, supportedPlatforms[k]))

DEVELOPMENT_BRANCH="10.10"
RELEASABLE_BRANCHES="5.5 10.0 10.1 10.2 10.3 10.4 10.5 10.6 bb-5.5-release bb-10.0-release bb-10.1-release bb-10.2-release bb-10.3-release bb-10.4-release bb-10.5-release bb-10.6-release"
savedPackageBranches= [
        "5.5",
        "10.0",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "10.6",
        "10.7",
        "10.8",
        "10.9",
        "10.10",
        "10.11",
        "bb-*-release",
        "bb-10.2-compatibility",
        "preview-*"]

# The trees for which we save binary packages.
releaseBranches = ["bb-*-release", "preview-10.*"]
