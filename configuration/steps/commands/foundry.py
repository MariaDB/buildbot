from pathlib import PurePath

from buildbot.plugins import util
from configuration.steps.commands.base import Command


class BuildPlugin(Command):
    # Pass package_type ("RPM" or "DEB") for the -D flag run.cmake expects,
    # or cmake_prefix_path (exclusive of package_type) to instead link
    # against an unpacked MariaDB server bintar via -DCMAKE_PREFIX_PATH --
    # omitting -DRPM/-DDEB entirely is what makes run.cmake produce a plain
    # bintar tarball for the plugin instead of a package.
    def __init__(
        self,
        package_type: str = None,
        cmake_prefix_path: str = None,
        workdir: PurePath = PurePath("."),
    ):
        assert (package_type is None) != (cmake_prefix_path is None), (
            "BuildPlugin takes exactly one of package_type or cmake_prefix_path"
        )
        self.package_type = package_type
        self.cmake_prefix_path = cmake_prefix_path
        super().__init__(
            name=f"Build plugin ({package_type or 'bintar'})", workdir=workdir
        )

    def as_cmd_arg(self) -> list[str]:
        cmake_define = (
            f"-DCMAKE_PREFIX_PATH={self.cmake_prefix_path} "
            if self.cmake_prefix_path
            else f"-D{self.package_type}=1 "
        )
        return [
            "bash",
            "-exc",
            util.Interpolate(f"cmake {cmake_define}-P run.cmake %(prop:plugin)s"),
        ]


class InstallBuiltPackages(Command):
    # Installs whatever run.cmake just built (copied next to run.cmake, see
    # run.cmake's `file(COPY ${packages} DESTINATION "${b}/..")`).
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(
            name=f"Install built plugin packages ({package_type})",
            workdir=workdir,
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        # apt-get/dnf can exit 0 having installed nothing (e.g. a malformed
        # package filename it silently ignores) -- verify each built package
        # actually landed, instead of only trusting the install command's
        # own exit code.
        if self.package_type == "RPM":
            script = """
dnf install -y ./*.rpm
for f in ./*.rpm; do
    pkg=$(rpm -qp --qf '%{NAME}' "$f")
    rpm -q "$pkg" >/dev/null 2>&1 || { echo "Package $pkg from $f was not installed" >&2; exit 1; }
done
"""
        else:
            script = """
apt-get install -y ./*.deb
for f in ./*.deb; do
    pkg=$(dpkg-deb -f "$f" Package)
    dpkg -s "$pkg" >/dev/null 2>&1 || { echo "Package $pkg from $f was not installed" >&2; exit 1; }
done
"""
        return ["bash", "-exc", f"set -euo pipefail\n{script}"]


class DownloadServerBintar(Command):
    # Foundry bintar plugin builds link against a matching MariaDB server
    # bintar instead of installed -devel packages. ci_builder is the
    # production buildbot builder on ci.mariadb.org that publishes it for
    # this OS (e.g. "amd64-centos-7-bintar") -- the exact tarball filename
    # varies by version/build, so it's discovered from the directory
    # listing rather than assumed. Emits the extracted directory's absolute
    # path on stdout, for capture into a property (e.g. via
    # PropFromShellStep) and use as BuildPlugin's cmake_prefix_path.
    def __init__(self, ci_builder: str, workdir: PurePath = PurePath(".")):
        self.ci_builder = ci_builder
        super().__init__(name="Download server bintar", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

base_url="https://ci.mariadb.org/%(prop:tarbuildnum)s/{self.ci_builder}"
# `... | head -1` here would let head close the pipe as soon as it has its
# one line, which under pipefail can turn curl/tar's resulting SIGPIPE into
# a hard failure of the whole step (seen in practice with tar -tzf listing a
# whole bintar's contents). `awk 'NR==1'` picks the same first line but
# still reads its input through to EOF, so the upstream command always
# exits normally instead of getting killed by a broken pipe.
filename=$(curl -fsSL "$base_url/" | grep -oE 'href="mariadb-[^"]*-linux[^"]*\\.tar\\.gz"' | sed -E 's/^href="(.*)"$/\\1/' | awk 'NR==1')
if [ -z "$filename" ]; then
    echo "Could not find a server bintar under $base_url" >&2
    exit 1
fi

mkdir -p /home/buildbot/bintar
curl -fsSL "$base_url/$filename" -o "/home/buildbot/bintar/$filename"
tar -xzf "/home/buildbot/bintar/$filename" -C /home/buildbot/bintar

dirname=$(tar -tzf "/home/buildbot/bintar/$filename" | awk -F/ 'NR==1{{print $1}}')
echo "/home/buildbot/bintar/$dirname"
"""
            ),
        ]


class ExtractPluginBintarIntoServerBintar(Command):
    # The plugin's own MTR suite is only visible to MTR once its bintar is
    # unpacked directly into the server bintar tree it was built against --
    # --strip-components=1 drops the plugin tarball's own top-level
    # directory so its plugin/<name>/ contents land alongside the server
    # bintar's own plugin/, mysql-test/, etc.
    #
    # The server bintar ships its own bundled plugin suites (rocksdb,
    # columnstore, ...) under that same plugin/*/*/suite.pm layout, so once
    # extraction is done there's no way to tell "ours" apart from those by
    # just re-scanning the merged tree. Emit the suite name(s) contributed
    # by *this* plugin's tarball -- read off its own listing, before it gets
    # merged in -- on stdout, for capture into a property (e.g. via
    # PropFromShellStep) and use as RunPluginMTRSuiteFromBintar's suites arg.
    def __init__(self, server_bintar_dir: str, workdir: PurePath = PurePath(".")):
        self.server_bintar_dir = server_bintar_dir
        super().__init__(
            name="Extract plugin bintar into server bintar", workdir=workdir
        )

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

suites=""
for f in ./mariadb-plugin-*.tar.gz; do
    tar -xf "$f" -C "{self.server_bintar_dir}" --strip-components=1
    for name in $(tar -tzf "$f" | grep -oE '^[^/]+/plugin/[^/]+/[^/]+/suite\\.pm$' | awk -F/ '{{print $4}}' || true); do
        suites="$suites,$name"
    done
done
suites=$(echo "$suites" | sed 's/^,//')
echo "$suites"
"""
            ),
        ]


class DiscoverPluginMTRSuites(Command):
    # MARIADB_ADD_PLUGIN's INSTALL_MYSQL_TEST (cmake/plugin.cmake) installs
    # a plugin's mysql-test suite(s) under <mtr_base_dir>/plugin/<X>/<name>/,
    # e.g. plugin/rocksdb/rocksdb/ or plugin/tidesdb/tidesdb/. <X> is the
    # plugin's own CMake source-dir name, which isn't always the same as the
    # Foundry "plugin" property (e.g. tidesql's is actually "tidesdb"), so
    # this discovers whatever actually landed under plugin/*/*/ rather than
    # guessing it. A suite dir is identified by its t/*.test files, not a
    # suite.pm -- suite.pm is optional (only needed for custom My::Suite
    # logic) and plenty of real suites, tidesdb's included, ship only
    # t/*.test + suite.opt/r/include and no suite.pm at all.
    #
    # This is the same plugin/*/*/ layout MariaDB-test itself uses for the
    # suites it bundles for its own plugins (rocksdb, columnstore,
    # auth_gssapi, ...). Once MariaDB-test is installed alongside our plugin
    # there's no way to tell "ours" apart by re-scanning the merged plugin/
    # directory -- doing that picked up every bundled suite as well as (or
    # instead of) the plugin actually under test. Read the suite name(s)
    # straight off the plugin's own just-built package listing instead,
    # before MariaDB-test ever gets installed. Emits comma-separated suite
    # name(s) on stdout for capture into a property (e.g. via
    # PropFromShellStep) and use as RunPluginMTRSuite's suites arg.
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(name="Discover plugin MTR suite", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        if self.package_type == "RPM":
            list_files_cmd = "rpm -qlp ./*.rpm"
        else:
            list_files_cmd = "dpkg-deb -c ./*.deb | awk '{print $NF}'"
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

suites=""
for path in $({list_files_cmd} | grep -oE '/plugin/[^/]+/[^/]+/t/[^/]+\\.test$' || true); do
    name=$(basename "$(dirname "$(dirname "$path")")")
    case ",$suites," in
        *",$name,"*) ;;
        *) suites="$suites,$name" ;;
    esac
done
suites=$(echo "$suites" | sed 's/^,//')
echo "$suites"
"""
            ),
        ]


class RunPluginMTRSuite(Command):
    # mtr_cases.pm resolves a bare suite name (e.g. "rocksdb") by searching
    # under plugin/*/ itself, so passing just the suite's short name is
    # enough -- no need to spell out the plugin/<X>/ prefix. suites is
    # discovered up front by DiscoverPluginMTRSuites, before MariaDB-test
    # gets installed -- see that class for why re-discovering it here, after
    # install, doesn't work. No suite for the plugin under test is skipped
    # rather than failing the build.
    #
    # On failure, logs are saved under save_logs_path -- default mirrors
    # _save_packages_step's layout in autobake.py (plugin/commit dir), with
    # a "logs" dir per builder underneath, e.g.
    # /packages/foundry/<mariadb_version>-<tarbuildnum>/<plugin>/<foundry_revision>/logs/<buildername>
    #
    # A subdir of the container's home, not /home/buildbot itself -- that's
    # the docker volume's own mount point, so MTR's "remove old var
    # directory" can never succeed there (Device or resource busy).
    MTR_VARDIR = "/home/buildbot/mtr-var"

    def __init__(
        self,
        package_type: str,
        suites: str,
        workdir: PurePath = PurePath("."),
        save_logs_path: str = (
            "/packages/foundry/%(prop:mariadb_version)s-%(prop:tarbuildnum)s"
            "/%(prop:plugin)s/%(prop:foundry_revision)s/logs/%(prop:buildername)s"
        ),
    ):
        self.package_type = package_type
        self.suites = suites
        self.save_logs_path = save_logs_path
        # Run unprivileged (the Command default, "buildbot"): galera SST's
        # rsync daemon only privilege-drops to nobody:nogroup when launched
        # by root (see rsyncd.conf(5) "uid"/"gid") -- wsrep_sst_rsync's
        # generated config never pins uid=/gid=, so a root-run mariadbd hits
        # that default and can't read the 0660 wsrep_* system tables during
        # SST. Running as buildbot keeps rsync at that same uid, which owns
        # those files, sidestepping the whole thing.
        super().__init__(name="Run plugin MTR suite", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # Ask the package manager where MariaDB-test/mariadb-test actually
        # put mariadb-test-run.pl, rather than guessing a path -- it's moved
        # across MariaDB package versions/layouts before. Match the current
        # top-level script by name, and exclude lib/v1/ specifically -- it
        # bundles its own legacy-named mysql-test-run.pl that isn't it.
        if self.package_type == "RPM":
            list_files_cmd = "rpm -ql MariaDB-test"
        else:
            list_files_cmd = "dpkg -L mariadb-test"
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

mtr_script=$({list_files_cmd} | grep -v '/lib/v1/' | grep -m1 '/mariadb-test-run\\.pl$' || true)
if [ -z "$mtr_script" ]; then
    echo "Could not locate mariadb-test-run.pl from the installed test package" >&2
    exit 1
fi
mtr_base_dir=$(dirname "$mtr_script")

suites="{self.suites}"
if [ -z "$suites" ]; then
    echo "No MTR suite found for plugin %(prop:plugin)s -- skipping"
    exit 0
fi

cd "$mtr_base_dir" && perl mariadb-test-run.pl --force --max-test-fail=20 --suite="$suites" --vardir={self.MTR_VARDIR} || ({self._save_logs()})
"""
            ),
        ]

    def _save_logs(self) -> str:
        # Mirrors MTRTest._save_logs (commands/mtr.py) for the "installed
        # packages" case: RunPluginMTRSuite always runs off installed
        # MariaDB-test/mariadb-test packages, never a build tree, so there's
        # no source-tree mariadbd fallback to try.
        logs = ["*.log", "*.err*", "core*"]
        patterns = " -o ".join([f'-iname "{log}"' for log in logs])
        return f"""
            vardir="{self.MTR_VARDIR}"
            save_logs_path="{self.save_logs_path}"
            file_patterns_to_save="{patterns}"

            if [ -d /usr/lib/mysql/plugin ]; then
                plugins_dir="/usr/lib/mysql/plugin"
            elif [ -d /usr/lib64/mysql/plugin ]; then
                plugins_dir="/usr/lib64/mysql/plugin"
            else
                plugins_dir="$vardir/plugins"
            fi
            mariadbd_path=$(command -v mariadbd 2>/dev/null || true)

            echo "Saving MTR logs"

            mkdir -p "$save_logs_path"

            # Save plugins .so and mariadbd if a core file was generated
            save_bin=0
            find $vardir -name *core.* -exec false {{}} + || save_bin=1
            if [[ $save_bin -ne 0 ]]; then
                plugins_list=$(mktemp)
                find -L "$plugins_dir" -maxdepth 1 -type f -name '*.so' -printf '%%f\\n' > "$plugins_list"
                tar -czvf "$save_logs_path/plugins.tar.gz" --dereference -C "$plugins_dir" -T "$plugins_list"
                rm -f "$plugins_list"
                [ -n "$mariadbd_path" ] && gzip -c "$mariadbd_path" > "$save_logs_path/mariadbd.gz"
            fi

            # Some core files are left uncompressed by MTR
            find $vardir -iregex ".*/core\\(\\.[0-9]+\\)?" -ls -exec gzip {{}} +

            # Archive matching log/core files into a single var.tar.gz --
            # same as the classic autobake server builders (see createVar()
            # in utils.py) -- instead of laying individual files out under
            # save_logs_path.
            cd "$vardir" && find . -type f \\( -path './log/*' -o $file_patterns_to_save \\) -print0 | tar -czf "$save_logs_path/var.tar.gz" --null -T -
            exit 1 # Script was invoked by an MTR failure so we must mark the step as failed
            """


class RunPluginMTRSuiteFromBintar(Command):
    # Runs the suite(s) contributed by the plugin we just built and unpacked
    # into a server bintar tree. Unlike RunPluginMTRSuite, suites isn't
    # (re)discovered here -- the server bintar bundles its own plugin
    # suites (rocksdb, columnstore, ...) under the same plugin/*/*/suite.pm
    # layout, so re-scanning the merged tree can't tell those apart from
    # ours. Instead suites comes straight from
    # ExtractPluginBintarIntoServerBintar, which read it off the plugin's
    # own tarball listing before merging. mariadb-test-run.pl (wrapped by
    # ./mtr) lives at a known path inside the tree, so there's no package
    # manager to query either.
    def __init__(
        self, server_bintar_dir: str, suites: str, workdir: PurePath = PurePath(".")
    ):
        self.server_bintar_dir = server_bintar_dir
        self.suites = suites
        super().__init__(name="Run plugin MTR suite", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

suites="{self.suites}"
if [ -z "$suites" ]; then
    echo "No MTR suite found for plugin %(prop:plugin)s -- skipping"
    exit 0
fi

cd "{self.server_bintar_dir}/mariadb-test" && ./mtr --force --max-test-fail=20 --suite="$suites"
"""
            ),
        ]
