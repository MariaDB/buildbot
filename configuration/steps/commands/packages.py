from pathlib import PurePath
from typing import Iterable, Union

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class CreateDebRepo(Command):
    """
    This class is used to create a local DEB repository.
    It generates the necessary files for a DEB repository
    and sets up the local APT source list.
    Attributes:
        url (str): The URL for the local DEB repository.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        url: str,
        workdir: PurePath = PurePath("."),
    ):
        name = "Create local DEB repository"
        super().__init__(name=name, workdir=workdir)
        self.url = url

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
    mkdir -p debs
    find . -maxdepth 1 -type f | xargs cp -t debs
    pushd debs
    apt-ftparchive packages . >Packages
    apt-ftparchive sources . >Sources
    apt-ftparchive release . >Release

    echo "deb [trusted=yes allow-insecure=yes] file:///home/buildbot/build/debs /" | sudo tee /etc/apt/sources.list
    sudo apt-get update

    popd
    cat << EOF > mariadb.sources
X-Repolib-Name: MariaDB
Types: deb
URIs: {self.url}/%(prop:tarbuildnum)s/%(prop:buildername)s/debs
Suites: ./
Trusted: yes
EOF
                    """,
            ),
        ]
        return result


# TODO (Razvan):This is a copy-paste only to showcase a full factory. Re-work needed.
class CreateRpmRepo(Command):
    """
    This class is used to create a local RPM repository.
    It generates the necessary files for an RPM repository
    and sets up the local YUM repository configuration.
    Attributes:
        rpm_type (str): The type of RPM repository (e.g., rhel8, centosstream8).
        url (str): The URL for the local RPM repository.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        rpm_type: str,
        url: str,
        workdir: PurePath = PurePath("."),
    ):
        name = "Create local RPM repository"
        super().__init__(name=name, workdir=workdir)
        self.rpm_type = rpm_type
        self.url = url

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
                if [ -e MariaDB-shared-10.1.*.rpm ]; then
                rm MariaDB-shared-10.1.*.rpm
                fi
                mkdir -p rpms srpms
                mv *.src.rpm srpms/
                mv *.rpm rpms/
                createrepo rpms/
                cat << EOF > MariaDB.repo
    [MariaDB-%(prop:branch)s]
    name=MariaDB %(prop:branch)s repo (build %(prop:tarbuildnum)s)
    baseurl={self.url}/%(prop:tarbuildnum)s/%(prop:buildername)s/rpms
    gpgcheck=0
    EOF
                if [ "{self.rpm_type}" = rhel8 ] || [ "{self.rpm_type}" = centosstream8 ] || [ "{self.rpm_type}" = almalinux8 ] || [ "{self.rpm_type}" = rockylinux8 ]; then
                    echo "module_hotfixes = 1" >> MariaDB.repo
                fi
                    """,
            ),
        ]
        return result


class SavePackages(Command):
    """
    This class is used to recursively copy a list of files and dirs to CI,
    starting from the current working directory and
    assuming that /packages is bind mounted.
    """

    def __init__(
        self,
        packages: list[str],
        workdir: PurePath = PurePath("."),
        destination: str = "/packages/%(prop:tarbuildnum)s/%(prop:buildername)s",
        user: str = "buildbot",
    ):
        name = "Save packages"
        self.packages = packages
        self.destination = destination
        super().__init__(name=name, workdir=workdir, user=user)

    def as_cmd_arg(self) -> list[str]:
        package_list = " ".join(self.packages)
        result = [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
                mkdir -p {self.destination} &&
                for package in {package_list}; do
                    if [ ! -e "$package" ]; then
                        echo "Warning: package '$package' does not exist and will be skipped."
                        continue
                    fi
                    cp -r $package {self.destination}
                done
                """
            ),
        ]
        return result


class InstallRPMFromProp(Command):
    """
    This class is used to install RPM packages from a property.
    It reads the list of packages from a specified property
    and installs them using the yum package manager.
    Attributes:
        property_name (str): The name of the property containing the list of packages.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        property_name: str,
        workdir: PurePath = PurePath("."),
    ):
        name = "Install RPM Packages"
        self.property_name = property_name
        super().__init__(name=name, workdir=workdir, user="root")

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
                    yum -y --nogpgcheck install %(kw:packages)s

                    if [ -d "/usr/share/mysql-test" ]; then
                        ln -s /usr/share/mysql-test /usr/share/mariadb-test
                    fi
                    """,
                packages=util.Property(self.property_name),
            ),
        ]
        return result


class InstallDEB(Command):
    """
    This class is used to install DEB packages from a specified file.
    It reads the list of packages from a file and installs them using the apt package manager.
    Attributes:
        packages_file (str): The path to the file containing the list of DEB packages.
        workdir (PurePath): The working directory for the command.
    """

    def __init__(
        self,
        packages_file: str,
        workdir: PurePath = PurePath("."),
    ):
        self.packages_file = packages_file
        super().__init__(name="Install DEB Packages", workdir=workdir, user="root")

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            f"""
                package_list=$(grep "^Package:" {self.packages_file} | grep -vE 'galera|spider|columnstore' | awk '{{print $2}}' | xargs)
DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 apt-get -o Debug::pkgProblemResolver=1 -o Dpkg::Options::=--force-confnew install --allow-unauthenticated -y $package_list

                if [ -d "/usr/share/mysql/mysql-test" ]; then
                    ln -s /usr/share/mysql/ /usr/share/mariadb
                    ln -s /usr/share/mysql/mysql-test /usr/share/mariadb/mariadb-test
                fi
                """,
        ]
        return result


class ArchiveSource(Command):
    def __init__(
        self,
        input_dir: PurePath,
        output_dir: PurePath,
        tarball_name: str,
        generate_sha256: bool = False,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.tarball_name = tarball_name
        self.generate_sha256 = generate_sha256
        super().__init__(name="Archive source code", workdir=input_dir)

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-exc",
            f"""
            mkdir -p {self.output_dir}
            tar --exclude-vcs --exclude {self.output_dir} -czf {self.output_dir}/{self.tarball_name} -C {self.input_dir} .
            {f"sha256sum {self.output_dir}/{self.tarball_name} > {self.output_dir}/sha256sums.txt" if self.generate_sha256 else ""}
            """,
        ]
        return result


class SetupDEBRepo(Command):
    def __init__(self, repo_name: str, repo_url: str, components: str = "main"):
        self.repo_name = repo_name
        self.repo_url = repo_url.rstrip("/")
        self.components = components

        super().__init__(
            name=f"Setup DEB repository: {repo_name}",
            workdir=PurePath("."),
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail
apt-get update
apt-get install -y apt-utils apt-transport-https ca-certificates

# Detect suite dynamically
. /etc/os-release
SUITE="$VERSION_CODENAME"

# Normalize base URL (remove /dists/<suite> if present)
BASE_URL="$(echo "{self.repo_url}" | sed -E 's#/dists/[^/]+/?$##')"

# Add repo
echo "deb [trusted=yes] $BASE_URL/$ID $SUITE {self.components}" \
  > /etc/apt/sources.list.d/{self.repo_name}.list

# Highest priority
cat > /etc/apt/preferences.d/{self.repo_name} <<EOF
Package: *
Pin: origin "$(echo "$BASE_URL" | awk -F/ '{{print $3}}')"
Pin-Priority: 1001
EOF

apt-get update
""",
        ]


class SetupRPMRepo(Command):
    def __init__(
        self, repo_name: str, repo_url: str, name: str = "Setup RPM repository"
    ):
        self.repo_name = repo_name
        self.repo_url = repo_url.rstrip("/")

        super().__init__(
            name=name,
            workdir=PurePath("."),
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

# Detect package manager
if command -v dnf >/dev/null 2>&1; then
    PKG_MGR="dnf"
elif command -v yum >/dev/null 2>&1; then
    PKG_MGR="yum"
elif command -v zypper >/dev/null 2>&1; then
    PKG_MGR="zypper"
else
    echo "Unsupported RPM-based system"
    exit 1
fi

source /etc/os-release
case $ID in
  rhel|almalinux|rocky)
    base_version=${{VERSION_ID%%.*}}
  ;;
  *)
    base_version=$VERSION_ID
  ;;
esac
base_id=$ID
url_path="$base_id/$base_version/$(rpm --eval '%_arch')"

# Create repo file
cat > /etc/yum.repos.d/{self.repo_name}.repo <<EOF
[{self.repo_name}]
name={self.repo_name}
baseurl={self.repo_url}/$url_path
enabled=1
gpgcheck=0
priority=1
module_hotfixes = 1
EOF

# Refresh metadata
if [ "$PKG_MGR" = "zypper" ]; then
    zypper --gpg-auto-import-keys refresh
else
    $PKG_MGR makecache
fi
""",
        ]


class InstallDEBPackages(Command):
    def __init__(
        self, packages: Union[str, Iterable[str]], workdir: PurePath = PurePath(".")
    ):
        if isinstance(packages, str):
            self.packages = [packages]
        else:
            self.packages = list(packages)

        super().__init__(
            name="Install DEB packages",
            workdir=workdir,
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        pkg_str = " ".join(self.packages)

        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y {pkg_str}
""",
        ]


class InstallRPMPackages(Command):
    def __init__(
        self,
        packages: Union[str, Iterable[str]],
        workdir: PurePath = PurePath(
            ".",
        ),
        name: str = "Install RPM packages",
    ):
        if isinstance(packages, str):
            self.packages = [packages]
        else:
            self.packages = list(packages)

        super().__init__(
            name=name,
            workdir=workdir,
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        pkg_str = " ".join(self.packages)

        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

if command -v dnf >/dev/null 2>&1; then
    dnf install -y {pkg_str}
elif command -v yum >/dev/null 2>&1; then
    yum install -y {pkg_str}
elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install {pkg_str}
else
    echo "Unsupported RPM-based system"
    exit 1
fi
""",
        ]
