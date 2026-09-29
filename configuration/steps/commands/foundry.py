import re
from pathlib import PurePath

from twisted.internet import defer

from buildbot.plugins import util
from buildbot.process import logobserver
from buildbot.process.results import FAILURE, SUCCESS, WARNINGS, Results
from configuration.steps.commands.base import Command, ShellCommandWithURL
from git_auth import git_auth_args

# Plugin lists reach the scripts as environment variables rather than through
# util.Interpolate, so the scripts can use % freely (rpm --qf '%{NAME}').
PLUGINS_ENV = "FOUNDRY_PLUGINS"
BUILT_PLUGINS_ENV = "FOUNDRY_BUILT_PLUGINS"
# Read by DiscoverFoundryPlugins only.
BRANCH_ENV = "FOUNDRY_BRANCH"
BASE_BRANCH_ENV = "FOUNDRY_BASE_BRANCH"

# Commands take a plugin's packages from its own <plugin>.build/: run.cmake
# also copies all of them into the workspace root, where they can't be told
# apart.
#
# plugin_installed <plugin> succeeds if all its packages are installed. Uses
# %{NAME}, so it can't go into an Interpolate'd script.
_PLUGIN_INSTALLED = {
    "RPM": """
plugin_installed() {
    for f in "$1.build"/*.rpm; do
        pkg=$(rpm -qp --qf '%{NAME}' "$f")
        rpm -q "$pkg" >/dev/null 2>&1 || { echo "$pkg ($f) is not installed" >&2; return 1; }
    done
}
""",
    # dpkg -s also succeeds for a package whose postinst failed.
    "DEB": """
plugin_installed() {
    for f in "$1.build"/*.deb; do
        pkg=$(dpkg-deb -f "$f" Package)
        status=$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)
        [ "$status" = "install ok installed" ] || { echo "$pkg ($f) is not installed: ${status:-absent}" >&2; return 1; }
    done
}
""",
}

# remove_plugin <plugin> removes what a failed install left of its packages,
# without their scripts, which may fail as well. Else apt retries a failed
# postinst on every later install, and suite discovery sees the package.
_REMOVE_PLUGIN = {
    "RPM": """
remove_plugin() {
    for f in "$1.build"/*.rpm; do
        pkg=$(rpm -qp --qf '%{NAME}' "$f")
        if rpm -q "$pkg" >/dev/null 2>&1; then
            rpm -e --nodeps --noscripts --notriggers "$pkg"
        fi
    done
}
""",
    "DEB": """
remove_plugin() {
    for f in "$1.build"/*.deb; do
        pkg=$(dpkg-deb -f "$f" Package)
        dpkg-query -W "$pkg" >/dev/null 2>&1 || continue
        rm -f /var/lib/dpkg/info/"$pkg".prerm /var/lib/dpkg/info/"$pkg".postrm \\
            /var/lib/dpkg/info/"$pkg":*.prerm /var/lib/dpkg/info/"$pkg":*.postrm
        dpkg --purge --force-all "$pkg"
    done
}
""",
}


def _print_suites(package_glob: str, list_files: str, only_if: str = None) -> str:
    # Shell that prints the built plugins' MTR suites, comma-separated and
    # once each, or logs that a plugin has none. They are read from the file
    # lists (list_files, of "$f") of each plugin's package_glob files; only_if
    # skips a plugin "$p" for which it fails. A suite is a
    # plugin/<x>/<suite>/ directory with t/*.test files; suite.pm is optional.
    # add_suites is fed by process substitution, so bash -x doesn't trace the
    # list.
    skip = f"\n    {only_if} || continue" if only_if else ""
    return f"""
add_suites() {{
    found=""
    for path in $(grep -oE '/plugin/[^/]+/[^/]+/t/[^/]+\\.test$' || true); do
        found=1
        name=$(basename "$(dirname "$(dirname "$path")")")
        case ",$suites," in
            *",$name,"*) ;;
            *) suites="$suites,$name" ;;
        esac
    done
    if [ -z "$found" ]; then echo "$1 has no MTR suite, so it won't be tested" >&2; fi
}}

suites=""
for p in ${{{BUILT_PLUGINS_ENV}}}; do{skip}
    add_suites "$p" < <(for f in {package_glob}; do [ -e "$f" ] && {list_files}; done)
done
echo "${{suites#,}}"
"""


class DiscoverFoundryPlugins(Command):
    # Prints the plugins to build: every top-level directory with a
    # CMakeLists.txt or, for a pull request, those it changes (all of them if
    # it changes the top-level build files). Changed files come from git, as
    # the GitHub hook doesn't record them for pull requests. Empty output
    # means nothing to build.
    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Discover foundry plugins", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # No Interpolate: the script uses ${d%/}.
        auth = git_auth_args()
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail

# Those of the given directories that are plugins.
plugins_in() {{
    out=""
    for d in "$@"; do
        d=${{d%/}}
        if [ -f "$d/CMakeLists.txt" ]; then out="$out $d"; fi
    done
    echo $out
}}

case "${{{BRANCH_ENV}:-}}" in
    refs/pull/*) ;;
    *) plugins_in */; exit 0 ;;
esac

# Diff from where the PR forked off its base branch; the default branch if
# GitHub gave none (a PR ref forced by hand). Authenticated like the clone,
# which keeps no credentials; see git_auth.py.
base="${{{BASE_BRANCH_ENV}:-}}"
if [ -z "$base" ]; then
    base=$(git {auth} remote show origin | sed -n 's/^ *HEAD branch: //p')
fi
git {auth} fetch --quiet origin "+refs/heads/$base:refs/foundry-base"
changed=$(git diff --name-only "$(git merge-base refs/foundry-base HEAD)" HEAD)

if echo "$changed" | grep -qxE 'CMakeLists\\.txt|run\\.cmake'; then
    plugins_in */
else
    plugins_in $(echo "$changed" | cut -d/ -f1 | sort -u)
fi
""",
        ]


class ArchiveFoundrySource(Command):
    # Writes a `git archive` of the checked-out commit to archive (under
    # /packages, which nginx serves) with a sha256sums.txt, and prints its
    # SHA-256. Refuses submodules, which git archive would leave out.
    def __init__(self, archive: str, workdir: PurePath = PurePath(".")):
        self.archive = archive
        super().__init__(name="Archive Foundry", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

if [ -n "$(git submodule status)" ]; then
    echo "Foundry has submodules, which git archive would leave out" >&2
    exit 1
fi

archive="{self.archive}"
dir=$(dirname "$archive")
name=$(basename "$archive")
mkdir -p "$dir"
git archive --format=tar.gz --prefix=foundry/ -o "$archive" HEAD
cd "$dir"
sha256sum "$name" > sha256sums.txt
cut -d' ' -f1 sha256sums.txt
"""
            ),
        ]


class DownloadFoundrySource(Command):
    # Fetches the dispatcher's archive, checks its SHA-256 and unpacks it into
    # the workdir. Retries in case the artifacts server doesn't serve it yet.
    ATTEMPTS = 5

    def __init__(self, url: str, sha256: str, workdir: PurePath = PurePath(".")):
        self.url = url
        self.sha256 = sha256
        super().__init__(name="Download Foundry", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

url="{self.url}"
sha256="{self.sha256}"
if [ -z "$url" ] || [ -z "$sha256" ]; then
    echo "No Foundry archive to download: only the dispatcher can start this build" >&2
    exit 1
fi

archive=foundry.tar.gz
attempt=1
until curl -fsSL -o "$archive" "$url" && echo "$sha256  $archive" | sha256sum -c -; do
    if [ "$attempt" -ge {self.ATTEMPTS} ]; then
        echo "Could not download $url with the expected SHA-256" >&2
        exit 1
    fi
    sleep $((attempt * 10))
    attempt=$((attempt + 1))
done
tar -xzf "$archive" --strip-components=1
rm -f "$archive"
"""
            ),
        ]


class BuildPlugins(Command):
    # Builds all of $FOUNDRY_PLUGINS in one run.cmake call, which carries on
    # past a failed plugin. Run it with BuildPluginsShellCommand, which reads
    # each plugin's outcome from run.cmake's summary.
    #
    # package_type ("RPM" or "DEB") builds packages; cmake_prefix_path instead
    # builds a bintar against the server bintar there. make runs one job per
    # CPU the builder is allotted (the jobs property).
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
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

plugins="${{{PLUGINS_ENV}}}"
if [ -z "$plugins" ]; then
    echo "No plugins to build" >&2
    exit 1
fi

echo "Building: $plugins"
CMAKE_BUILD_PARALLEL_LEVEL=%(prop:jobs:-1)s cmake {cmake_define}-P run.cmake $plugins
"""
            ),
        ]


class FoundrySummary:
    # Parses the summary run.cmake prints at the end:
    #   -- FOUNDRY-RESULT: PASS <plugin> <package file>...
    #   -- FOUNDRY-RESULT: FAIL <plugin> <configure|build|package> <reason>
    #   -- FOUNDRY-SUMMARY: <failed> of <total> plugins failed
    _LINE = re.compile(r"-- FOUNDRY-(RESULT|SUMMARY): (.*)")

    def __init__(self):
        self.built = []  # plugins, from PASS lines
        self.failures = {}  # plugin -> "<stage>: <reason>", from FAIL lines
        self.complete = False  # the FOUNDRY-SUMMARY line was seen

    # Runs on the reactor thread for every output line, so most lines stop at
    # the startswith.
    def feed(self, line: str):
        if not line.startswith("-- FOUNDRY-"):
            return
        match = self._LINE.fullmatch(line.rstrip())
        if not match:
            return
        kind, rest = match.groups()
        if kind == "SUMMARY":
            self.complete = True
            return
        fields = rest.split()
        if len(fields) < 2:
            return
        verdict, plugin, details = fields[0], fields[1], fields[2:]
        if verdict == "PASS":
            self.built.append(plugin)
        elif verdict == "FAIL":
            stage, *reason = details or ["unknown"]
            self.failures[plugin] = f"{stage}: {' '.join(reason)}"

    def evaluate(self, requested: list[str], command_ok: bool):
        # Returns (result, built plugins, {failed plugin: why}, description).
        built = list(self.built)
        failures = dict(self.failures)
        # run.cmake silently skips any argument with a dot in it.
        for plugin in requested:
            if plugin not in built and plugin not in failures:
                failures[plugin] = "not reported by run.cmake"
        if not self.complete:
            return FAILURE, built, failures, "run.cmake printed no summary"

        description = f"built {len(built)} of {len(built) + len(failures)} plugins"
        if failures:
            description += "; failed: " + ", ".join(
                f"{plugin} ({why})" for plugin, why in failures.items()
            )
        if not built:
            return FAILURE, built, failures, description
        if failures:
            return WARNINGS, built, failures, description
        if not command_ok:
            # Every plugin passed, yet cmake failed: see the log.
            return FAILURE, built, failures, f"{description}, but cmake failed"
        return SUCCESS, built, failures, description


class _FoundrySummaryObserver(logobserver.LogLineObserver):
    # stdout only: stderr has bash -x echoing the script.
    def __init__(self, summary: FoundrySummary):
        super().__init__()
        self.summary = summary

    def outLineReceived(self, line):
        self.summary.feed(line)


class BuildPluginsShellCommand(ShellCommandWithURL):
    # The step for BuildPlugins, as ShellStep's step_class. Its result comes
    # from the summary: SUCCESS if every plugin built, WARNINGS if some did
    # (pair with flunkOnWarnings), FAILURE if none did or there's no summary.
    # Sets built_plugins. A stopped step records nothing.
    #
    # Buildbot 2.x (the production fork) decides in evaluateCommand(); 3.0+
    # only calls run(). 2.x calls run() too, as its bridge to start(), hence
    # `concluded`.
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.foundry_summary = FoundrySummary()
        self.concluded = False
        self.verdict_line = None
        self.addLogObserver("stdio", _FoundrySummaryObserver(self.foundry_summary))

    # Buildbot 2.x
    def evaluateCommand(self, cmd):
        return self._conclude(cmd.results())

    # Buildbot 3.0+
    @defer.inlineCallbacks
    def run(self):
        result = yield super().run()
        if self.concluded:  # 2.x: evaluateCommand() already ran
            return result
        # 3.0+ finishes logs after run(); flush stdio for the observer.
        stdio = yield self.getLog("stdio")
        yield stdio.finish()
        return self._conclude(result)

    def _conclude(self, command_result) -> int:
        self.concluded = True
        if self.stopped:
            # Cut short: the missing summary says nothing about the plugins.
            return command_result
        requested = str(self.getProperty("foundry_plugins") or "").split()
        result, built, _, self.verdict_line = self.foundry_summary.evaluate(
            requested, command_ok=command_result == SUCCESS
        )
        self.setProperty("built_plugins", " ".join(built), self.name)
        return result

    def getResultSummary(self):
        if self.verdict_line is None:
            return super().getResultSummary()
        summary = self.verdict_line
        if self.results != SUCCESS:
            summary += f" ({Results[self.results]})"
        return {"step": summary}


class InstallBuiltPackages(Command):
    # Installs each built plugin separately, so one that won't install doesn't
    # sink the rest, and checks its packages really landed: apt/dnf can exit 0
    # having skipped a file. A failed install script fails the plugin too, and
    # a failed plugin is removed again. Exits 0 if all installed, 2 if some
    # did (see ShellStep.PARTIAL_SUCCESS_DECODE_RC), 1 if none did.
    #
    # Paths start with ./ because apt reads "a.build/x.deb" as package
    # "a.build" from release "x.deb".
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(
            name=f"Install built plugin packages ({package_type})",
            workdir=workdir,
            user="root",
        )

    def as_cmd_arg(self) -> list[str]:
        if self.package_type == "RPM":
            install = """
if command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install --allow-unsigned-rpm ./"$1.build"/*.rpm || return 1
else
    # dnf only warns when an install script fails; zypper exits 107.
    log=$(mktemp)
    dnf install -y ./"$1.build"/*.rpm 2>&1 | tee "$log" || return 1
    if grep -qE 'scriptlet failed|Error in [A-Z]+ scriptlet' "$log"; then return 1; fi
fi"""
        else:
            install = """
apt-get install -y ./"$1.build"/*.deb || return 1"""
        # No Interpolate: _PLUGIN_INSTALLED uses %{NAME}.
        return [
            "bash",
            "-exc",
            f"""
set -uo pipefail
{_PLUGIN_INSTALLED[self.package_type]}
{_REMOVE_PLUGIN[self.package_type]}
install_plugin() {{{install}
    plugin_installed "$1"
}}

plugins="${{{BUILT_PLUGINS_ENV}}}"
if [ -z "$plugins" ]; then
    echo "No built plugins to install" >&2
    exit 1
fi

installed=""
failed=""
for p in $plugins; do
    echo "--- Installing $p"
    if install_plugin "$p"; then
        installed="$installed $p"
    else
        failed="$failed $p"
        remove_plugin "$p"
    fi
done

echo "Installed:${{installed:- (none)}}"
echo "Failed:   ${{failed:- (none)}}"
if [ -z "$installed" ]; then exit 1; fi
if [ -n "$failed" ]; then exit 2; fi
""",
        ]


class PrepareBaseImage(Command):
    # Packages are tested in the target's plain base image, so this adds only
    # what the pipeline needs: the buildbot user with the worker uid, to own
    # the workspace volume (--non-unique: some bases have a uid 1000 already);
    # ca-certificates and curl on apt bases; findutils on zypper, for saving
    # MTR logs. Plus ps, which MariaDB needs but doesn't declare: galera SST
    # hangs without it (wsrep_sst_rsync runs "ps -p"). Drop it once MariaDB
    # declares the dependency.
    WORKER_UID = 1000

    def __init__(self, workdir: PurePath = PurePath(".")):
        super().__init__(name="Prepare base image", workdir=workdir, user="root")

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail
id -u buildbot >/dev/null 2>&1 || useradd --non-unique --uid {self.WORKER_UID} \\
    --no-create-home --home-dir /home/buildbot buildbot
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl procps
elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install findutils procps
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y procps-ng
elif command -v yum >/dev/null 2>&1; then
    yum install -y procps-ng
fi
""",
        ]


class SavePluginPackages(Command):
    # Copies each built plugin's packages to destination, whose literal
    # $plugin the shell fills in, with a sha256sums.txt for them.
    def __init__(self, destination: str, workdir: PurePath = PurePath(".")):
        self.destination = destination
        super().__init__(name="Save packages", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # $saved is unquoted to split into file names (CPack names have no
        # spaces), and checked first: sha256sum with no files reads stdin.
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

for plugin in ${{{BUILT_PLUGINS_ENV}}}; do
    destination="{self.destination}"
    mkdir -p "$destination"
    saved=""
    for f in "$plugin.build"/*.rpm "$plugin.build"/*.deb "$plugin.build"/*.tar.gz "$plugin.build"/*.zip; do
        [ -e "$f" ] || continue
        cp -r "$f" "$destination"
        saved="$saved $(basename "$f")"
    done
    if [ -n "$saved" ]; then
        (cd "$destination" && sha256sum $saved > sha256sums.txt)
    fi
done
"""
            ),
        ]


# Shared tail of both server bintar downloads: fetches the bintar listed at
# $base_url, unpacks it into /home/buildbot/bintar and prints its directory.
_FETCH_SERVER_BINTAR = """
filename=$(curl -fsSL "$base_url/" | grep -oE 'href="mariadb-[^"]*-linux[^"]*\\.tar\\.gz"' | sed -E 's/^href="(.*)"$/\\1/' | awk 'NR==1' || true)
if [ -z "$filename" ]; then
    echo "Could not find a server bintar under $base_url" >&2
    exit 1
fi

mkdir -p /home/buildbot/bintar
dirname=$(curl -fsSL "$base_url/$filename" | tar -xzvf - -C /home/buildbot/bintar | awk -F/ 'NR==1{print $1}')
echo "/home/buildbot/bintar/$dirname"
"""


class DownloadServerBintar(Command):
    # The CI server builder's bintar, from base_url
    # (<ci_url>/<tarbuildnum>/<server builder>).
    def __init__(self, base_url: str, workdir: PurePath = PurePath(".")):
        self.base_url = base_url
        super().__init__(name="Download CI bintar", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

base_url="{self.base_url}"
{_FETCH_SERVER_BINTAR}
"""
            ),
        ]


class DownloadServerBintarFromMirror(Command):
    # The mirrors' mirror_bintar of the newest release of mariadb_version. The
    # mirrors carry only one, x86_64 flavour, hence amd64-only bintar targets.
    def __init__(
        self, mirror_url: str, mirror_bintar: str, workdir: PurePath = PurePath(".")
    ):
        self.mirror_url = mirror_url
        self.mirror_bintar = mirror_bintar
        super().__init__(name="Download mirror bintar", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

# Newest point release (mariadb-11.4.13/); dots escaped so 11.4 can't match 1104.
version_re=$(echo "%(prop:mariadb_version)s" | sed 's/\\./\\\\./g')
release=$(curl -fsSL "{self.mirror_url}/" | grep -oE "href=\\"mariadb-${{version_re}}\\.[0-9]+/\\"" | sed -E 's|^href="mariadb-(.*)/"$|\\1|' | sort -V | tail -1 || true)
if [ -z "$release" ]; then
    echo "No MariaDB %(prop:mariadb_version)s release found on {self.mirror_url}" >&2
    exit 1
fi

base_url="{self.mirror_url}/mariadb-$release/{self.mirror_bintar}"
{_FETCH_SERVER_BINTAR}
"""
            ),
        ]


class ExtractPluginBintarIntoServerBintar(Command):
    # Unpacks each built plugin's bintar into the server bintar, where MTR
    # finds its suites, and prints those suites, comma-separated. They are read
    # from the plugin tarballs: the server bintar has suites of its own in the
    # same layout.
    def __init__(self, server_bintar_dir: str, workdir: PurePath = PurePath(".")):
        self.server_bintar_dir = server_bintar_dir
        super().__init__(name="Extract plugin bintar", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail

for p in ${{{BUILT_PLUGINS_ENV}}}; do
  for f in "$p.build"/*.tar.gz; do
    [ -e "$f" ] || continue
    tar -xf "$f" -C "{self.server_bintar_dir}" --strip-components=1
  done
done
{_print_suites('"$p.build"/*.tar.gz', 'tar -tzf "$f"')}"""
            ),
        ]


class DiscoverPluginMTRSuites(Command):
    # Prints the MTR suites of the built plugins that installed,
    # comma-separated. Read from their packages before MariaDB-test lands,
    # since it ships suites of its own in the same layout. A plugin that
    # didn't install is left out: MTR aborts on a --suite it can't find.
    def __init__(self, package_type: str, workdir: PurePath = PurePath(".")):
        self.package_type = package_type
        super().__init__(name="Discover plugin MTR suites", workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        # One package at a time: dpkg-deb -c takes just one.
        if self.package_type == "RPM":
            list_files_cmd = 'rpm -qlp "$f"'
            package_glob = '"$p.build"/*.rpm'
        else:
            list_files_cmd = "dpkg-deb -c \"$f\" | awk '{print $NF}'"
            package_glob = '"$p.build"/*.deb'
        return [
            "bash",
            "-exc",
            f"""
set -euo pipefail
{_PLUGIN_INSTALLED[self.package_type]}
{_print_suites(package_glob, list_files_cmd, only_if='plugin_installed "$p"')}""",
        ]


# MTR's var directory. Not /home/buildbot itself: that is the volume's mount
# point, which MTR can't remove.
_MTR_VARDIR = "/home/buildbot/mtr-var"


def _save_mtr_logs(save_logs_path: str, find_binaries: str) -> str:
    # Shell for after a failed MTR run: packs the logs into
    # save_logs_path/var.tar.gz, plus the plugins and mariadbd if a core was
    # dumped, then fails the step. find_binaries sets $plugins_dir and
    # $mariadbd_path.
    logs = ["*.log", "*.err*", "core*"]
    patterns = " -o ".join([f"-iname '{log}'" for log in logs])
    return f"""
            vardir="{_MTR_VARDIR}"
            save_logs_path="{save_logs_path}"
            {find_binaries}
            if [ ! -d "$vardir" ]; then
                echo "MTR failed before running any test, left no logs to save"
                exit 1
            fi
            echo "Saving MTR logs"

            mkdir -p "$save_logs_path"

            # Save plugins .so and mariadbd if a core file was generated:
            # core, core.<pid>, or either compressed.
            if [ -n "$(find "$vardir" -type f \\( -name core -o -name 'core.*' \\) -print -quit)" ]; then
                plugins_list=$(mktemp)
                find -L "$plugins_dir" -maxdepth 1 -type f -name '*.so' -printf '%%f\\n' > "$plugins_list"
                tar -czvf "$save_logs_path/plugins.tar.gz" --dereference -C "$plugins_dir" -T "$plugins_list"
                rm -f "$plugins_list"
                [ -f "$mariadbd_path" ] && gzip -c "$mariadbd_path" > "$save_logs_path/mariadbd.gz"
            fi

            # Some core files are left uncompressed by MTR
            find "$vardir" -iregex ".*/core\\(\\.[0-9]+\\)?" -ls -exec gzip {{}} +

            cd "$vardir" && find . -type f \\( -path './log/*' -o {patterns} \\) -print0 | tar -czf "$save_logs_path/var.tar.gz" --null -T -
            exit 1 # Script was invoked by an MTR failure so we must mark the step as failed
            """


class _RunPluginMTR(Command):
    # Runs every suite in one MTR run (--force). On failure the logs go to
    # save_logs_path. Subclasses give the shell that cds to
    # mariadb-test-run.pl, and find_binaries for _save_mtr_logs.
    def __init__(
        self, suites: str, save_logs_path: str, workdir: PurePath = PurePath(".")
    ):
        self.suites = suites
        self.save_logs_path = save_logs_path
        # Not root: galera SST's rsync then drops to nobody, which can't read
        # the 0660 wsrep_* tables.
        super().__init__(name="Run plugin MTR suite", workdir=workdir)

    def _cd_to_mtr(self) -> str:
        raise NotImplementedError

    def _find_binaries(self) -> str:
        raise NotImplementedError

    def as_cmd_arg(self) -> list[str]:
        return [
            "bash",
            "-exc",
            util.Interpolate(
                f"""
set -euo pipefail
{self._cd_to_mtr()}
perl mariadb-test-run.pl --force --max-test-fail=20 --suite="{self.suites}" --vardir={_MTR_VARDIR} || ({_save_mtr_logs(self.save_logs_path, self._find_binaries())})
"""
            ),
        ]


class RunPluginMTRSuite(_RunPluginMTR):
    # From the installed test package.
    def __init__(self, package_type: str, suites: str, save_logs_path: str):
        self.package_type = package_type
        super().__init__(suites, save_logs_path)

    def _cd_to_mtr(self) -> str:
        # Ask the package where mariadb-test-run.pl is; lib/v1/ has an old one.
        if self.package_type == "RPM":
            list_files_cmd = "rpm -ql MariaDB-test"
        else:
            list_files_cmd = "dpkg -L mariadb-test"
        return f"""
mtr_script=$({list_files_cmd} | grep -v '/lib/v1/' | grep -m1 '/mariadb-test-run\\.pl$' || true)
if [ -z "$mtr_script" ]; then
    echo "Could not locate mariadb-test-run.pl from the installed test package" >&2
    exit 1
fi
cd "$(dirname "$mtr_script")"
"""

    def _find_binaries(self) -> str:
        return """
            if [ -d /usr/lib/mysql/plugin ]; then
                plugins_dir="/usr/lib/mysql/plugin"
            elif [ -d /usr/lib64/mysql/plugin ]; then
                plugins_dir="/usr/lib64/mysql/plugin"
            else
                plugins_dir="$vardir/plugins"
            fi
            mariadbd_path=$(command -v mariadbd 2>/dev/null || true)"""


class RunPluginMTRSuiteFromBintar(_RunPluginMTR):
    # Runs the suites ExtractPluginBintarIntoServerBintar found, inside the
    # server bintar.
    def __init__(self, server_bintar_dir: str, suites: str, save_logs_path: str):
        self.server_bintar_dir = server_bintar_dir
        super().__init__(suites, save_logs_path)

    def _cd_to_mtr(self) -> str:
        return f'cd "{self.server_bintar_dir}/mariadb-test"'

    def _find_binaries(self) -> str:
        return (
            f'plugins_dir="{self.server_bintar_dir}/lib/plugin"; '
            f'mariadbd_path="{self.server_bintar_dir}/bin/mariadbd"'
        )
