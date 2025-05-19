from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class CreateDebRepo(Command):
    def __init__(
        self,
        url: str,
        buildername: str,
        workdir: PurePath = PurePath("."),
    ):
        name = "Create local DEB repository"
        super().__init__(name=name, workdir=workdir)
        self.url = url
        self.buildername = buildername

    def as_cmd_arg(self) -> list[str]:
        result = [
            "bash",
            "-ec",
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
URIs: {self.url}/%(prop:tarbuildnum)s/{self.buildername}/debs
Suites: ./
Trusted: yes
EOF
                    """,
            ),
        ]
        return result


# TODO (Razvan):This is a copy-paste only to showcase a full factory. Re-work needed.
class CreateRpmRepo(Command):
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
            "-ec",
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
    ):
        name = "Save packages"
        self.packages = packages
        self.destination = destination
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        package_list = " ".join(self.packages)
        result = [
            "bash",
            "-ec",
            util.Interpolate(
                f"""
                mkdir -p {self.destination} &&
                cp -r {package_list} {self.destination}
                """
            ),
        ]
        return result


class InstallRPMFromProp(Command):
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
            "-ec",
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
            "-ec",
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
