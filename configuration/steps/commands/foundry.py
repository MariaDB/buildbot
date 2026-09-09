from pathlib import PurePath

from buildbot.plugins import util

from configuration.steps.commands.base import Command

# Plugin lists reach these commands through the environment rather than
# util.Interpolate, so their scripts stay free of Interpolate's %-escaping --
# several of them would otherwise have to mangle rpm --qf '%{NAME}' and
# find -printf '%f'. autobake.py builds the matching env_vars entries.
PLUGINS_ENV = "FOUNDRY_PLUGINS"
BUILT_PLUGINS_ENV = "FOUNDRY_BUILT_PLUGINS"
INSTALLED_PLUGINS_ENV = "FOUNDRY_INSTALLED_PLUGINS"
# Only DiscoverFoundryPlugins reads these two.
BRANCH_ENV = "FOUNDRY_BRANCH"
BASE_BRANCH_ENV = "FOUNDRY_BASE_BRANCH"

# Shared by every command that has to tell apart the plugins that built from
# the ones that didn't.
#
# run.cmake takes a list of plugins and keeps going after one fails --
# message(SEND_ERROR), not FATAL_ERROR -- so a single invocation routinely
# leaves a mix behind. It copies every plugin's packages into the workspace
# root together (`file(COPY ${packages} DESTINATION "${b}/..")`), so the root
# can't tell you who produced what; each plugin's own build tree,
# <plugin>.build/, can. A package in there means that plugin built.
#
# Only sound on a fresh workspace: a package left over from an earlier run
# would read as a success. Every foundry builder starts from a clean
# container and checkout, so that holds here.
_PLUGIN_HELPERS = """
built_plugins() {
    out=""
    for p in $1; do
        for f in "$p.build"/*.rpm "$p.build"/*.deb "$p.build"/*.tar.gz; do
            if [ -e "$f" ]; then out="$out $p"; break; fi
        done
    done
    echo $out
}

# Everything in $1 that is not in $2.
missing_plugins() {
    out=""
    for p in $1; do
        case " $2 " in
            *" $p "*) ;;
            *) out="$out $p" ;;
        esac
    done
    echo $out
}

# Best-effort verdict shared by the build and install steps, reported through
# the exit code -- see ShellStep.PARTIAL_SUCCESS_DECODE_RC.
#   0  every plugin made it
#   2  some did, some didn't: a warning on the step, a failure on the build
#   1  none did: nothing downstream can do anything useful
verdict() {
    ok=$1
    bad=$2
    if [ -z "$ok" ]; then
        echo "$3" >&2
        exit 1
    fi
    if [ -n "$bad" ]; then
        echo "$4" >&2
        exit 2
    fi
    exit 0
}
"""


class DiscoverFoundryPlugins(Command):
    # Foundry registers one plugin per top-level directory with a
    # CMakeLists.txt in it (see its own run.cmake/README), so that is what
    # gets discovered rather than being listed anywhere in this repo -- adding
    # a plugin to Foundry is then all it takes to get it built.
    #
    # For a pull request, only the plugins the PR actually touches are built.
    # The changed files come from git in the checkout, not from buildbot's
    # Changed Files: this buildbot's GitHub hook doesn't populate those for
    # pull request events.
    #
    # Emits the plugin directory names, space-separated, on stdout -- for
    # capture into a property (e.g. via PropFromShellStep) and hand-off to
    # the package builders as $FOUNDRY_PLUGINS. Empty output means there is
    # nothing to build, which for a PR touching no plugin is a legitimate
    # outcome, not an error.
    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Discover foundry plugins", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # No Interpolate: the script uses ${d%/} and other %-expansions.
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

all_plugins() {{
    out=""
    for d in */; do
        if [ -f "$d/CMakeLists.txt" ]; then out="$out ${{d%/}}"; fi
    done
    echo $out
}}

case "${{{BRANCH_ENV}:-}}" in
    refs/pull/*) ;;
    *) all_plugins; exit 0 ;;
esac

# Pull request: diff against where it forked off its base branch. The base
# is whatever GitHub said the PR targets; falling back to the repository's
# default branch keeps this working for a run started by hand off a PR ref.
base="${{{BASE_BRANCH_ENV}:-}}"
if [ -z "$base" ]; then
    base=$(git remote show origin | sed -n 's/^ *HEAD branch: //p')
fi
git fetch --quiet origin "+refs/heads/$base:refs/foundry-base"
changed=$(git diff --name-only "$(git merge-base refs/foundry-base HEAD)" HEAD)

# The top-level build glue is not owned by any one plugin and affects all of
# them, so a change there means everything gets rebuilt.
if echo "$changed" | grep -qxE 'CMakeLists\\.txt|run\\.cmake'; then
    all_plugins
    exit 0
fi

out=""
for d in $(echo "$changed" | cut -d/ -f1 | sort -u); do
    if [ -f "$d/CMakeLists.txt" ]; then out="$out $d"; fi
done
echo $out
""",
        ]


class BuildPlugins(Command):
    # Pass package_type ("RPM" or "DEB") for the -D flag run.cmake expects,
    # or cmake_prefix_path (exclusive of package_type) to instead link
    # against an unpacked MariaDB server bintar via -DCMAKE_PREFIX_PATH --
    # omitting -DRPM/-DDEB entirely is what makes run.cmake produce a plain
    # bintar tarball for the plugin instead of a package.
    #
    # Builds every plugin the dispatcher discovered ($FOUNDRY_PLUGINS) in one
    # run.cmake invocation, which is what makes the best-effort behaviour
    # possible: run.cmake works through the whole list regardless of
    # individual failures, so one broken plugin doesn't hide the others'
    # results. cmake's own exit code only says "something failed", so the
    # verdict is recomputed per plugin from <plugin>.build/.
    def __init__(
        self,
        package_type: str = None,
        cmake_prefix_path: str = None,
        workdir: PurePath = PurePath("."),
    ):
        assert (package_type is None) != (
            cmake_prefix_path is None
        ), "BuildPlugins takes exactly one of package_type or cmake_prefix_path"
        self.package_type = package_type
        self.cmake_prefix_path = cmake_prefix_path
        super().__init__(
            name=f"Build plugins ({package_type or 'bintar'})", workdir=workdir
        )

    def as_cmd_arg(self) -> list[str]:
        cmake_define = (
            f"-DCMAKE_PREFIX_PATH={self.cmake_prefix_path} "
            if self.cmake_prefix_path
            else f"-D{self.package_type}=1 "
        )
        # Interpolate is needed for cmake_prefix_path, which is a property
        # reference; the rest of the script deliberately avoids % and {}.
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -uo pipefail
{_PLUGIN_HELPERS}
plugins="${{{PLUGINS_ENV}}}"
if [ -z "$plugins" ]; then
    echo "No plugins to build" >&2
    exit 1
fi

echo "Building: $plugins"
set +e
cmake {cmake_define}-P run.cmake $plugins
set -e

built=$(built_plugins "$plugins")
failed=$(missing_plugins "$plugins" "$built")

echo "Built:  ${{built:-(none)}}"
echo "Failed: ${{failed:-(none)}}"

verdict "$built" "$failed" \\
    "No plugin built -- see the cmake output above" \\
    "These plugins failed to build: $failed"
"""
            ),
        ]


class InstallBuiltPackages(Command):
    # Installs what BuildPlugins produced, one plugin at a time so a plugin
    # whose packages won't install doesn't take the others down with it --
    # a single `dnf/apt-get install ./*` over the workspace root would fail
    # the whole transaction. Each plugin's packages are taken from its own
    # <plugin>.build/ rather than the root copies, which is also what makes
    # them attributable to a plugin at all.
    #
    # Emits the same 0/2/1 best-effort verdict as BuildPlugins.
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
            install_plugin = """
install_plugin() {
    dnf install -y "$1.build"/*.rpm || return 1
    for f in "$1.build"/*.rpm; do
        pkg=$(rpm -qp --qf '%{NAME}' "$f")
        if ! rpm -q "$pkg" >/dev/null 2>&1; then
            echo "Package $pkg from $f was not installed" >&2
            return 1
        fi
    done
}
"""
        else:
            install_plugin = """
install_plugin() {
    apt-get install -y "$1.build"/*.deb || return 1
    for f in "$1.build"/*.deb; do
        pkg=$(dpkg-deb -f "$f" Package)
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "Package $pkg from $f was not installed" >&2
            return 1
        fi
    done
}
"""
        # No Interpolate here: the verification uses rpm --qf '%{NAME}',
        # which %-formatting would eat.
        return [
            "bash",
            "-exc",
            f"""
set -uo pipefail
{_PLUGIN_HELPERS}
{install_plugin}
plugins="${{{BUILT_PLUGINS_ENV}}}"
if [ -z "$plugins" ]; then
    echo "No built plugins to install" >&2
    exit 1
fi

installed=""
for p in $plugins; do
    echo "--- Installing $p"
    if install_plugin "$p"; then
        installed="$installed $p"
    else
        echo "Plugin $p failed to install" >&2
    fi
done
installed=$(echo $installed)
failed=$(missing_plugins "$plugins" "$installed")

echo "Installed: ${{installed:-(none)}}"
echo "Failed:    ${{failed:-(none)}}"

verdict "$installed" "$failed" \\
    "No plugin package could be installed" \\
    "These plugins failed to install: $failed"
""",
        ]


class ListPluginsWithPackages(Command):
    # Emits, space-separated on stdout, whichever of $FOUNDRY_PLUGINS left a
    # package in <plugin>.build/ -- for capture into a property (e.g. via
    # PropFromShellStep) so later steps can work off the plugins that
    # actually built rather than the ones that were asked for.
    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="List plugins that built", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail
{_PLUGIN_HELPERS}
built_plugins "${{{PLUGINS_ENV}}}"
""",
        ]


class ListInstalledPlugins(Command):
    # Emits, space-separated on stdout, whichever of $FOUNDRY_BUILT_PLUGINS
    # has all of its packages installed -- the same check
    # InstallBuiltPackages makes, re-run so the outcome can be captured into
    # a property. Suite discovery and MTR must skip plugins whose packages
    # never landed: their suite files aren't on disk, and MTR aborts the
    # whole run if a --suite entry doesn't exist.
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(name="List installed plugins", workdir=workdir, user="root")

    def as_cmd_arg(self) -> list[str]:
        if self.package_type == "RPM":
            is_installed = """
plugin_installed() {
    for f in "$1.build"/*.rpm; do
        pkg=$(rpm -qp --qf '%{NAME}' "$f")
        rpm -q "$pkg" >/dev/null 2>&1 || return 1
    done
}
"""
        else:
            is_installed = """
plugin_installed() {
    for f in "$1.build"/*.deb; do
        pkg=$(dpkg-deb -f "$f" Package)
        dpkg -s "$pkg" >/dev/null 2>&1 || return 1
    done
}
"""
        return [
            "bash",
            "-exc",
            f"""
set -uo pipefail
{is_installed}
out=""
for p in ${{{BUILT_PLUGINS_ENV}}}; do
    if plugin_installed "$p"; then out="$out $p"; fi
done
echo $out
""",
        ]


class SavePluginPackages(Command):
    # SavePackages' per-plugin counterpart: run.cmake pools every plugin's
    # packages in the workspace root, so copying that root would file all of
    # them under whichever plugin the path happens to name. Copy each
    # plugin's own <plugin>.build/ contents instead, so the saved layout
    # stays one directory per plugin.
    #
    # destination is rendered once, with a literal $plugin in it for the
    # per-plugin segment -- Interpolate only touches %(...)s, so the shell
    # variable survives rendering.
    def __init__(
        self,
        destination: str,
        workdir: PurePath = PurePath("."),
        user: str = "buildbot",
    ):
        self.destination = destination
        super().__init__(name="Save packages", workdir=workdir, user=user)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

for plugin in ${{{BUILT_PLUGINS_ENV}}}; do
    destination="{self.destination}"
    mkdir -p "$destination"
    for f in "$plugin.build"/*.rpm "$plugin.build"/*.deb "$plugin.build"/*.tar.gz; do
        [ -e "$f" ] || continue
        cp -r "$f" "$destination"
    done
done
"""
            ),
        ]


# Shared tail of both server-bintar downloads: given a $base_url whose
# directory listing holds exactly one server bintar, fetch it, unpack it
# under /home/buildbot/bintar and emit the extracted directory's absolute
# path on stdout -- for capture into a property (e.g. via PropFromShellStep)
# and use as BuildPlugins' cmake_prefix_path.
#
# The exact tarball filename varies by version/build, so it's discovered from
# the listing rather than assumed. `... | head -1` here would let head close
# the pipe as soon as it has its one line, which under pipefail can turn
# curl/tar's resulting SIGPIPE into a hard failure of the whole step (seen in
# practice with tar -tzf listing a whole bintar's contents). `awk 'NR==1'`
# picks the same first line but still reads its input through to EOF, so the
# upstream command always exits normally instead of getting killed by a
# broken pipe. The `|| true` is what lets the "not found" message below be
# reached at all -- without it `set -e` aborts on grep's empty-match exit 1
# before the check runs.
_FETCH_SERVER_BINTAR = """
filename=$(curl -fsSL "$base_url/" | grep -oE 'href="mariadb-[^"]*-linux[^"]*\\.tar\\.gz"' | sed -E 's/^href="(.*)"$/\\1/' | awk 'NR==1' || true)
if [ -z "$filename" ]; then
    echo "Could not find a server bintar under $base_url" >&2
    exit 1
fi

mkdir -p /home/buildbot/bintar
curl -fsSL "$base_url/$filename" -o "/home/buildbot/bintar/$filename"
tar -xzf "/home/buildbot/bintar/$filename" -C /home/buildbot/bintar

dirname=$(tar -tzf "/home/buildbot/bintar/$filename" | awk -F/ 'NR==1{print $1}')
echo "/home/buildbot/bintar/$dirname"
"""


class DownloadServerBintar(Command):
    # Foundry bintar plugin builds link against a matching MariaDB server
    # bintar instead of installed -devel packages. ci_builder is the
    # production buildbot builder on ci.mariadb.org that publishes it for
    # this OS (e.g. "amd64-centos-7-bintar").
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
{_FETCH_SERVER_BINTAR}
"""
            ),
        ]


class DownloadServerBintarFromMirror(Command):
    # DownloadServerBintar's counterpart for builds sourced from the MariaDB
    # Server mirrors, which have no tarbuildnum to fetch a CI bintar by.
    #
    # The mirrors publish one bintar per GA release, and only one flavour of
    # it -- bintar-linux-systemd-x86_64 -- which is the same tarball whoever
    # unpacks it, so there's no per-builder path here the way ci_builder is
    # on the CI side. That also means this only works for x86_64 builders;
    # the bintar packages in foundry.yaml are all arch: [amd64].
    MIRROR_URL = "https://mirror.mariadb.org"

    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Download server bintar", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

# Bintars live under a point release directory (mariadb-11.4.13/) with no
# directory for the branch itself, so resolve mariadb_version to its newest
# point release off the mirror's own listing. The version is escaped into the
# match so its dots can't act as regex wildcards (11.4 matching "1104").
version_re=$(echo "%(prop:mariadb_version)s" | sed 's/\\./\\\\./g')
release=$(curl -fsSL "{self.MIRROR_URL}/" | grep -oE "href=\\"mariadb-${{version_re}}\\.[0-9]+/\\"" | sed -E 's|^href="mariadb-(.*)/"$|\\1|' | sort -V | tail -1 || true)
if [ -z "$release" ]; then
    echo "No MariaDB %(prop:mariadb_version)s release found on {self.MIRROR_URL}" >&2
    exit 1
fi

base_url="{self.MIRROR_URL}/mariadb-$release/bintar-linux-systemd-x86_64"
{_FETCH_SERVER_BINTAR}
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
    # by the plugins' own tarballs -- read off their listings, before they
    # get merged in -- on stdout, for capture into a property (e.g. via
    # PropFromShellStep) and use as RunPluginMTRSuiteFromBintar's suites arg.
    #
    # Tarballs are taken per plugin from $FOUNDRY_BUILT_PLUGINS' own
    # <plugin>.build/ rather than globbed out of the workspace root, which
    # holds every plugin's output pooled together under whatever names their
    # CPack config chose.
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
for p in ${{{BUILT_PLUGINS_ENV}}}; do
  for f in "$p.build"/*.tar.gz; do
    [ -e "$f" ] || continue
    tar -xf "$f" -C "{self.server_bintar_dir}" --strip-components=1
    for name in $(tar -tzf "$f" | grep -oE '^[^/]+/plugin/[^/]+/[^/]+/suite\\.pm$' | awk -F/ '{{print $4}}' || true); do
        suites="$suites,$name"
    done
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
    # Foundry plugin directory (e.g. tidesql's is actually "tidesdb"), so
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
    #
    # Only $FOUNDRY_INSTALLED_PLUGINS are scanned, and each from its own
    # <plugin>.build/: a plugin that built but whose packages wouldn't
    # install has no suite files on disk, and one missing --suite entry
    # makes MTR abort the entire run rather than skip it.
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(name="Discover plugin MTR suites", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # rpm -qlp takes any number of packages, but dpkg-deb --contents takes
        # exactly one, so both list one package at a time -- a plugin
        # routinely ships more than one (its own package plus a -dbgsym).
        if self.package_type == "RPM":
            list_files_cmd = 'rpm -qlp "$f"'
            package_glob = '"$p.build"/*.rpm'
        else:
            # Plain string, not an f-string: its braces are not re-escaped
            # when it is substituted into the script below.
            list_files_cmd = "dpkg-deb -c \"$f\" | awk '{print $NF}'"
            package_glob = '"$p.build"/*.deb'
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

suites=""
for p in ${{{INSTALLED_PLUGINS_ENV}}}; do
  for f in {package_glob}; do
    [ -e "$f" ] || continue
    for path in $({list_files_cmd} | grep -oE '/plugin/[^/]+/[^/]+/t/[^/]+\\.test$' || true); do
      name=$(basename "$(dirname "$(dirname "$path")")")
      case ",$suites," in
          *",$name,"*) ;;
          *) suites="$suites,$name" ;;
      esac
    done
  done
done
suites=$(echo "$suites" | sed 's/^,//')
echo "$suites"
""",
        ]


class RunPluginMTRSuite(Command):
    # mtr_cases.pm resolves a bare suite name (e.g. "rocksdb") by searching
    # under plugin/*/ itself, so passing just the suite's short name is
    # enough -- no need to spell out the plugin/<X>/ prefix. suites is
    # discovered up front by DiscoverPluginMTRSuites, before MariaDB-test
    # gets installed -- see that class for why re-discovering it here, after
    # install, doesn't work, and why it only covers the plugins that
    # installed. No suites at all means nothing testable survived the build
    # and install; that's skipped rather than failed, since the steps that
    # dropped those plugins have already failed the build themselves.
    #
    # Every suite runs in one MTR invocation (with --force, so one plugin's
    # failing test doesn't stop the others), which is why the logs below are
    # per run rather than per plugin.
    #
    # On failure, logs are saved under save_logs_path -- the commit dir from
    # _save_packages_step's layout in autobake.py, with a "logs" dir per
    # builder underneath, e.g.
    # /packages/foundry/<mariadb_version>-<tarbuildnum>/<foundry_revision>/logs/<buildername>
    # A build sourced from the MariaDB Server mirrors has no tarbuildnum and
    # uses "mirror" in its place -- keep this in step with _SERVER_SOURCE in
    # autobake.py, which builds the matching artifacts URL.
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
            "/packages/foundry/%(prop:mariadb_version)s-%(prop:tarbuildnum:~mirror)s"
            "/%(prop:foundry_revision)s/logs/%(prop:buildername)s"
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
    echo "No MTR suite found for any built plugin -- skipping"
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
    echo "No MTR suite found for any built plugin -- skipping"
    exit 0
fi

cd "{self.server_bintar_dir}/mariadb-test" && ./mtr --force --max-test-fail=20 --suite="$suites"
"""
            ),
        ]
