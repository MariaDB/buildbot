import fnmatch
import os
import re
from datetime import datetime
from typing import Any, Generator, Tuple

import docker
from twisted.internet import defer, threads
from twisted.python import log

from buildbot.buildrequest import BuildRequest
from buildbot.data.resultspec import Filter
from buildbot.interfaces import IProperties
from buildbot.master import BuildMaster
from buildbot.plugins import steps, util, worker
from buildbot.process.builder import Builder
from buildbot.process.buildstep import BuildStep
from buildbot.process.results import CANCELLED, FAILURE, SUCCESS
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from buildbot.worker import AbstractWorker
from constants import (
    ALL_BB_TEST_BRANCHES,
    BUILDERS_AUTOBAKE,
    BUILDERS_ECO,
    BUILDERS_GALERA_MTR,
    BUILDERS_INSTALL,
    BUILDERS_S3_MTR,
    BUILDERS_UPGRADE,
    DEVELOPMENT_BRANCH,
    MTR_ENV,
    RELEASE_BRANCHES,
    SAVED_PACKAGE_BRANCHES,
    STAGING_PROT_TEST_BRANCHES,
)

private_config = {"private": {}}
exec(open("/srv/buildbot/master/master-private.cfg").read(), private_config, {})


def envFromProperties(envlist: list[str]) -> dict[str, str]:
    d = {}
    for e in envlist:
        d[e] = util.Interpolate(f"%(prop:{e})s")
    d["tarbuildnum"] = util.Interpolate("%(prop:tarbuildnum)s")
    d["development_branch"] = DEVELOPMENT_BRANCH
    return d


def getScript(
    scriptname: str, branch: str = os.environ["BRANCH"]
) -> steps.ShellCommand:
    return steps.ShellCommand(
        name=f"fetch_{scriptname}",
        command=[
            "bash",
            "-exc",
            f"""
  for script in bash_lib.sh {scriptname}; do
    [[ ! -f $script ]] && wget "https://raw.githubusercontent.com/MariaDB/buildbot/{branch}/scripts/$script"
  done
  chmod a+x {scriptname}
            """,
        ],
    )


# BUILD HELPERS
MASTER_PACKAGES = os.environ["MASTER_PACKAGES_DIR"]


# Helper function that creates a worker instance.
def createWorker(
    worker_name_prefix: str,
    worker_id: str,
    worker_type: str,
    dockerfile: str,
    jobs: int = 5,
    save_packages: bool = False,
    shm_size: str = "15G",
    worker_name_suffix: str = "",
    volumes: list[str] = [
        "/srv/buildbot/ccache:/mnt/ccache",
        "/srv/buildbot/packages:/mnt/packages",
        MASTER_PACKAGES + "/:/packages",
    ],
) -> Tuple[str, str, worker.DockerLatentWorker]:
    worker_name = f"{worker_name_prefix}{worker_id}-docker"
    name = f"{worker_name}-{worker_type}{worker_name_suffix}"

    # TODO(cvicentiu) Remove this list when refactoring YAML.
    b_name = worker_name_prefix
    X64_BUILDER_PREFIXES = ["hz", "intel", "amd", "apexis", "ns"]
    PPC64LE_BUILDER_PREFIXES = ["ppc64le"]
    for x64_prefix in X64_BUILDER_PREFIXES:
        if worker_name_prefix.startswith(x64_prefix):
            b_name = "x64-bbw"
    for ppc_prefix in PPC64LE_BUILDER_PREFIXES:
        if worker_name_prefix.startswith(ppc_prefix):
            b_name = "ppc64le-bbw"

    base_name = f"{b_name}-docker-{worker_type}"

    # Set master FQDN - default to wireguard interface
    fqdn = os.environ["BUILDMASTER_WG_IP"]
    if re.match("aarch64-bbw[1-4]", worker_name):
        fqdn = "buildbot.mariadb.org"
    dockerfile_str = None
    image_str = dockerfile
    dockerfile_url = "docker pull " + dockerfile
    need_pull = True

    worker_instance = worker.DockerLatentWorker(
        name,
        None,
        docker_host=private_config["private"]["docker_workers"][worker_name],
        image=image_str,
        dockerfile=dockerfile_str,
        tls=None,
        autopull=True,
        alwaysPull=need_pull,
        followStartupLogs=False,
        masterFQDN=fqdn,
        build_wait_timeout=0,
        missing_timeout=600,
        max_builds=1,
        hostconfig={
            "shm_size": shm_size,
            "ulimits": [
                docker.types.Ulimit(name="memlock", soft=51200000, hard=51200000)
            ],
        },
        volumes=volumes,
        properties={
            "jobs": jobs,
            "save_packages": save_packages,
            "dockerfile": dockerfile_url,
        },
    )
    return (base_name, name, worker_instance)


def printEnv() -> steps.ShellCommand:
    return steps.ShellCommand(
        name="Environment details",
        command=[
            "bash",
            "-c",
            util.Interpolate(
                """
            date -u
            uname -a
            ulimit -a
            command -v systemctl >/dev/null && systemctl --version
            command -v lscpu >/dev/null && lscpu
            LD_SHOW_AUXV=1 sleep 0
            """
            ),
        ],
    )


def getSourceTarball() -> steps.ShellCommand:
    return steps.ShellCommand(
        name="get_tarball",
        description="get source tarball",
        descriptionDone="get source tarball...done",
        haltOnFailure=True,
        env={"ARTIFACTS_URL": os.environ["ARTIFACTS_URL"]},
        command=[
            "bash",
            "-ec",
            util.Interpolate(read_template("get_tarball")),
        ],
    )


def saveLogs() -> steps.ShellCommand:
    return steps.ShellCommand(
        name="Save logs",
        description="saving logs",
        descriptionDone="save logs...done",
        alwaysRun=True,
        haltOnFailure=True,
        env={"ARTIFACTS_URL": os.environ["ARTIFACTS_URL"]},
        command=[
            "bash",
            "-ec",
            util.Interpolate(read_template("save_logs")),
        ],
    )


def createDebRepo() -> steps.ShellCommand:
    return steps.ShellCommand(
        name="Create deb repository",
        haltOnFailure=True,
        command=[
            "bash",
            "-exc",
            util.Interpolate(
                """
    mkdir ../debs
    find .. -maxdepth 1 -type f | xargs cp -t ../debs
    cd ../debs
    apt-ftparchive packages . >Packages
    apt-ftparchive sources . >Sources
    apt-ftparchive release . >Release
"""
            ),
        ],
        doStepIf=(
            lambda step: hasPackagesGenerated(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
        ),
    )


def uploadDebArtifacts() -> steps.ShellCommand:
    return steps.ShellCommand(
        name="Upload artifacts",
        timeout=7200,
        haltOnFailure=True,
        command=[
            "bash",
            "-exc",
            util.Interpolate(
                """
    artifacts_url="""
                + os.environ["ARTIFACTS_URL"]
                + """
    . /etc/os-release
    if [[ $ID == "debian" ]]; then
      COMPONENTS="main"
    else
      COMPONENTS="main main/debug"
    fi
    mkdir -p /packages/%(prop:tarbuildnum)s/%(prop:buildername)s
    cp -r ../debs /packages/%(prop:tarbuildnum)s/%(prop:buildername)s/
    cat << EOF > /packages/%(prop:tarbuildnum)s/%(prop:buildername)s/mariadb.sources
X-Repolib-Name: MariaDB
Types: deb
URIs: $artifacts_url/%(prop:tarbuildnum)s/%(prop:buildername)s/debs
Suites: ./
Trusted: yes
EOF
    cat /packages/%(prop:tarbuildnum)s/%(prop:buildername)s/mariadb.sources
    ln -sf %(prop:tarbuildnum)s/%(prop:buildername)s/mariadb.sources \
        /packages/%(prop:branch)s-latest-%(prop:buildername)s.sources
    sync /packages/%(prop:tarbuildnum)s
    """
            ),
        ],
        doStepIf=(
            lambda step: hasPackagesGenerated(step)
            and savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES)
        ),
        descriptionDone=util.Interpolate(
            """
            Use """
            + os.environ["ARTIFACTS_URL"]
            + """/%(prop:tarbuildnum)s/%(prop:buildername)s/mariadb.sources for testing.
            """
        ),
    )


def fnmatch_any(branch: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(branch, pattern) for pattern in patterns)


def upstream_branch_fn(branch):
    return fnmatch_any(branch, ALL_BB_TEST_BRANCHES)


def staging_branch_fn(branch: str) -> bool:
    return fnmatch_any(branch, STAGING_PROT_TEST_BRANCHES)


# Priority filter based on saved package branches
def nextBuild(builder: Builder, requests: list[BuildRequest]) -> BuildRequest:
    def build_request_sort_key(request: BuildRequest):
        branch = request.sources[""].branch
        # Booleans are sorted False first.
        # Priority is given to releaseBranches, savePackageBranches
        # then it's first come, first serve.
        return (
            not fnmatch_any(branch, RELEASE_BRANCHES),
            not fnmatch_any(branch, SAVED_PACKAGE_BRANCHES),
            request.getSubmitTime(),
        )

    return min(requests, key=build_request_sort_key)


def canStartBuild(
    builder: Builder, wfb: AbstractWorkerForBuilder, request: BuildRequest
) -> bool:
    return True


@util.renderer
def mtrJobsMultiplier(props: IProperties) -> int:
    jobs = props.getProperty("jobs", default=20)
    return jobs * 2


# ls2string gets the output of ls and returns a space delimited string with
# the files and directories
def ls2string(rc: int, stdout: str, stderr: str) -> dict[str, str]:
    ls_filenames = []
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line:
            ls_filenames.append(line)

    return {"packages": " ".join(ls_filenames)}


# ls2list gets the output of ls and returns a list with the files and
# directories
def ls2list(rc: int, stdout: str, stderr: str) -> dict[str, list[str]]:
    ls_filenames = []

    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line:
            ls_filenames.append(line)

    return {"packages": ls_filenames}


# Save packages for current branch?
def savePackageIfBranchMatch(step: BuildStep, branch_match: str) -> bool:
    return step.getProperty("save_packages") and fnmatch_any(
        step.getProperty("branch"), branch_match
    )


# Return a HTML file that contains links to MTR logs
def getHTMLLogString(base_path: str = "./buildbot") -> str:
    return f"""
mkdir -p {base_path}
echo '<!DOCTYPE html>
<html>
<body>' >> {base_path}/mysql_logs.html

echo '<a href="{os.environ['ARTIFACTS_URL']}/%(prop:tarbuildnum)s/logs/%(prop:buildername)s/">logs (mariadbd.gz + var.tar.gz)</a><br>' >> {base_path}/mysql_logs.html

echo '</body>
</html>' >> {base_path}/mysql_logs.html"""


def hasFailed(step: BuildStep) -> bool:
    return step.build.results == FAILURE


def createVar(base_path: str = "./buildbot", output_dir: str = "") -> str:
    return f"""
if [[ -d ./mysql-test/var ]]; then
  typeset -r var_tarball_list="var_tarball_list.txt"
  if [[ -f $var_tarball_list ]]; then
    rm $var_tarball_list
  fi
  touch $var_tarball_list

  # save defaults logs
  echo "mysql-test/var/log" >>$var_tarball_list
  find mysql-test/var/*/log -name "*.err" -o -name "*.log" >>$var_tarball_list

  # save core dumps
  find ./mysql-test/var/ -name "core*" >>$var_tarball_list

  # save binaries (if not already saved by another mtr failing test)
  if [[ -f sql/mysqld ]] && [[ ! -L sql/mysqld ]]; then
    [[ -f "./{base_path}/logs/mysqld.gz" ]] ||
      gzip -c sql/mysqld >"./{base_path}/logs/mysqld.gz"
  fi
  if [[ -f sql/mariadbd ]]; then
    [[ -f "./{base_path}/logs/mariadbd.gz" ]] ||
      gzip -c sql/mariadbd >"./{base_path}/logs/mariadbd.gz"
  fi

  tar czvf var.tar.gz -T ./$var_tarball_list
  mv var.tar.gz "./{base_path}/logs/{output_dir}"
fi"""


# Function to move the MTR logs to a known location so that they can be saved
def moveMTRLogs(base_path: str = "./buildbot", output_dir: str = "") -> str:
    return f"""
mkdir -p {base_path}/logs/{output_dir}

filename="mysql-test/var/log/mysqld.1.err"
if [ -f $filename ]; then
   cp $filename {base_path}/logs/{output_dir}/mysqld.1.err
fi

mtr=1
mysqld=1

while true
do
  while true
  do
    logname="mysqld.$mysqld.err.$mtr"
    filename="mysql-test/var/$mtr/log/mysqld.$mysqld.err"
    if [ -f $filename ]; then
       cp $filename {base_path}/logs/{output_dir}/$logname
    else
       break
    fi
    mysqld=$(( mysqld + 1 ))
  done
  mysqld=1
  mtr=$(( mtr + 1 ))
  filename="mysql-test/var/$mtr/log/mysqld.$mysqld.err"
  if [ ! -f $filename ]
  then
    break
  fi
done"""


# checks if the list of files is empty
def hasPackagesGenerated(step: BuildStep) -> bool:
    return len(step.getProperty("packages")) >= 1


def hasInstall(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_INSTALL:
        if builder_name in b:
            return True
    return False


def hasUpgrade(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_UPGRADE:
        if builder_name in b:
            return True
    return False


def hasEco(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_ECO:
        if builder_name in b:
            return True
    return False


def hasCompat(step: BuildStep) -> bool:
    buildername = str(step.getProperty("buildername"))
    major = int(step.getProperty("master_branch").split(".")[0])
    arch = buildername.split("-")[0]

    return (
        any(b in buildername for b in ("rhel-7", "rhel-8"))
        and major < 11
        and arch != "s390x"
    )


def hasDockerLibrary(step: BuildStep) -> bool:
    # Can only build with a saved package
    if not savePackageIfBranchMatch(step, SAVED_PACKAGE_BRANCHES):
        return False

    branch = step.getProperty("master_branch")
    builder_name = step.getProperty("buildername")

    # from https://github.com/MariaDB/mariadb-docker/blob/next/update.sh#L7-L15
    if fnmatch.fnmatch(branch, "10.11") or fnmatch.fnmatch(branch, "10.6"):
        dockerbase = "ubuntu-2204-deb-autobake"
    elif fnmatch.fnmatch(branch, "11.*") or fnmatch.fnmatch(branch, "12.2"):
        dockerbase = "ubuntu-2404-deb-autobake"
    else:
        dockerbase = "ubuntu-2604-deb-autobake"

    # UBI images
    if builder_name.endswith("amd64-rhel-9-rpm-autobake"):
        return fnmatch.fnmatch(branch, "10.*") or fnmatch.fnmatch(branch, "11.*")

    if builder_name.endswith("amd64-rhel-10-rpm-autobake"):
        return not (fnmatch.fnmatch(branch, "10.*") or fnmatch.fnmatch(branch, "11.*"))

    # We only build on the above autobakes for all architectures
    return builder_name.endswith(dockerbase)


def filterBranch(step: BuildStep) -> str:
    if "10.6" in step.getProperty("branch"):
        return False
    return True


# check if branch is a staging branch
def isStagingBranch(step: BuildStep) -> bool:
    return staging_branch_fn(step.getProperty("branch"))


# set step's waitForFinish to True if staging branch
def waitIfStaging(step: BuildStep) -> bool:
    if isStagingBranch(step):
        step.waitForFinish = True
    return True


def hasAutobake(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_AUTOBAKE:
        if builder_name in b:
            return True
    return False


def hasGalera(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_GALERA_MTR:
        if builder_name in b:
            return True
    return False


def hasS3(props):
    builder_name = props.getProperty("buildername")
    for b in BUILDERS_S3_MTR:
        if builder_name == b:
            return True
    return False


def hasRpmLint(step: BuildStep) -> str:
    builder_name = step.getProperty("buildername")
    if "sles-1600" in builder_name:
        return False
    return True


@util.renderer
def getArch(props: IProperties) -> str:
    buildername = props.getProperty("buildername")
    return buildername.split("-")[0]


# Builder priority
#
# Prioritize builders. At this point, only the Windows builders need a higher
# priority since the others run on dedicated machines.
def prioritizeBuilders(
    buildmaster: BuildMaster, builders: list[Builder]
) -> list[Builder]:
    """amd64-windows-* builders should have the highest priority since they are
    used for protected branches"""
    builderPriorities = {
        "amd64-windows": 0,
        "amd64-windows-packages": 1,
    }
    builders.sort(key=lambda b: builderPriorities.get(b.name, 2))
    return builders


def read_template(template_name: str) -> str:
    with open(f"/srv/buildbot/master/script_templates/{template_name}.sh") as f:
        return f.read()


def isJepsenBranch(step: BuildStep) -> bool:
    return step.getProperty("branch").startswith("jpsn")


def isTxnTesterBranch(step: BuildStep) -> bool:
    return step.getProperty("branch").startswith("txn")


@util.renderer
def mtrEnv(props: IProperties) -> dict:
    """
    Renders the MTR environment variables.

    If mtr_env property is set it will return a dictionary
    with the merged values of the default MTR_ENV and the mtr_env property,
    otherwise the default MTR_ENV constant will be returned.

    Args:
        props (object): The properties object.

    Returns:
        dict: The rendered MTR environment.
    """
    if props.hasProperty("mtr_env"):
        mtr_add_env = props.getProperty("mtr_env")
        for key, value in MTR_ENV.items():
            if key not in mtr_add_env:
                mtr_add_env[key] = value
        return mtr_add_env
    return MTR_ENV


class CancelDuplicateBuildRequests(BuildStep):
    """Stop duplicate push builds when a matching pull request build exists.

    When GitHub sends push and pull_request events for the same commit, both can
    queue tarball-docker requests. A normal branch push should yield to a matching
    pull request buildrequest on the same builder.
    """

    name = "cancel duplicate buildrequests"
    description = ["checking duplicate buildrequests"]
    descriptionDone = ["duplicate buildrequests checked"]

    def __init__(
        self,
        dry_run=False,
        buildbot_base_url=None,
        recent_completed_limit=10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.dry_run = dry_run
        self.recent_completed_limit = recent_completed_limit
        self.buildbot_base_url = (
            buildbot_base_url.rstrip("/") if buildbot_base_url else None
        )
        self._builder_name_cache = {}

    def _buildrequest_url(self, brid):
        if not self.buildbot_base_url:
            return None
        return f"{self.buildbot_base_url}/#/buildrequests/{brid}"

    @staticmethod
    def _fmt_ss(ss):
        return (
            f"branch={ss.get('branch')!r}, "
            f"repository={ss.get('repository')!r}, "
            f"revision={ss.get('revision')!r}, "
            f"codebase={ss.get('codebase', '')!r}"
        )

    @staticmethod
    def _branch_rejection_reasons(branch):
        """Explain why a branch push must not yield to a pull request build."""
        reasons = []

        if not branch:
            return ["branch is missing"]

        branch_lc = branch.lower()
        if len(branch) <= 5:
            reasons.append(
                f"branch is only {len(branch)} characters; it must be longer than 5"
            )
        if branch_lc.startswith("refs/"):
            reasons.append("branch starts with 'refs/'")

        matching_patterns = [
            pattern
            for pattern in SAVED_PACKAGE_BRANCHES
            if fnmatch.fnmatch(branch, pattern)
        ]
        if matching_patterns:
            reasons.append(
                f"branch matches saved-package pattern(s) {matching_patterns!r}"
            )

        return reasons

    @classmethod
    def _branch_is_cancelable(cls, branch):
        """Only let disposable normal branch pushes yield to pull request builds."""
        return not cls._branch_rejection_reasons(branch)

    @classmethod
    def _sourcestamp_rejection_reasons(cls, ss):
        reasons = []
        if ss.get("revision") is None:
            reasons.append("revision is missing")
        reasons.extend(cls._branch_rejection_reasons(ss.get("branch")))
        return reasons

    @defer.inlineCallbacks
    def _find_pull_request_matches(self, buildrequests, current_targets, source):
        matches = []

        for br in buildrequests:
            other_buildsetid = br["buildsetid"]
            other_buildset = yield self.master.data.get(("buildsets", other_buildsetid))
            other_sourcestamps = other_buildset.get("sourcestamps", [])

            matched_revision = None
            matched_branch = None

            for other_ss in other_sourcestamps:
                other_revision = other_ss.get("revision")
                other_branch = other_ss.get("branch")
                other_target = (
                    other_revision,
                    other_ss.get("repository"),
                    other_ss.get("codebase", ""),
                )

                if not other_branch or not other_branch.startswith("refs/pull/"):
                    continue

                if other_target in current_targets:
                    matched_revision = other_revision
                    matched_branch = other_branch
                    break

            if matched_revision is None:
                continue

            matches.append(
                {
                    "buildrequestid": br["buildrequestid"],
                    "claimed": br.get("claimed"),
                    "complete": br.get("complete"),
                    "buildsetid": other_buildsetid,
                    "revision": matched_revision,
                    "branch": matched_branch,
                    "url": self._buildrequest_url(br["buildrequestid"]),
                    "sourcestamps": other_sourcestamps,
                    "source": source,
                }
            )

        return matches

    @defer.inlineCallbacks
    def run(self):
        lines = []
        lines.append(f"Mode: {'DRY-RUN' if self.dry_run else 'ACTIVE'}")
        lines.append("")

        event = self.getProperty("event", None)
        lines.append(f"event property: {event!r}")

        if event is None:
            lines.append("No 'event' property found; nothing to do.")
            self.addCompleteLog("duplicate-buildrequests", "\n".join(lines) + "\n")
            return SUCCESS

        if event != "push":
            lines.append("Event is not 'push'; nothing to do.")
            self.addCompleteLog("duplicate-buildrequests", "\n".join(lines) + "\n")
            return SUCCESS

        current_buildid = self.build.buildid
        current_build = yield self.master.data.get(("builds", current_buildid))

        current_buildrequestid = current_build["buildrequestid"]
        current_builderid = current_build["builderid"]

        current_buildrequest = yield self.master.data.get(
            ("buildrequests", current_buildrequestid)
        )
        current_buildsetid = current_buildrequest["buildsetid"]

        current_buildset = yield self.master.data.get(("buildsets", current_buildsetid))
        current_sourcestamps = current_buildset.get("sourcestamps", [])

        if not current_sourcestamps:
            lines.append("Current buildset has no sourcestamps; nothing to do.")
            self.addCompleteLog("duplicate-buildrequests", "\n".join(lines) + "\n")
            return SUCCESS

        current_targets = {
            (ss.get("revision"), ss.get("repository"), ss.get("codebase", ""))
            for ss in current_sourcestamps
            if ss.get("revision") is not None
            and self._branch_is_cancelable(ss.get("branch"))
        }

        if not current_targets:
            lines.append(
                "No current sourcestamp is eligible for duplicate cancellation; "
                "nothing to do."
            )
            lines.append("Sourcestamp rejection details:")
            for i, ss in enumerate(current_sourcestamps, 1):
                reasons = self._sourcestamp_rejection_reasons(ss)
                lines.append(f"  [{i}] {self._fmt_ss(ss)}")
                lines.extend(f"      - {reason}" for reason in reasons)
            self.addCompleteLog("duplicate-buildrequests", "\n".join(lines) + "\n")
            return SUCCESS

        current_branches = {
            ss.get("branch")
            for ss in current_sourcestamps
            if ss.get("branch") is not None
        }

        lines.append("Current:")
        lines.append(f"  buildid={current_buildid}")
        lines.append(f"  buildrequestid={current_buildrequestid}")
        lines.append(f"  builderid={current_builderid}")
        lines.append(f"  buildsetid={current_buildsetid}")
        lines.append(f"  targets={sorted(current_targets)!r}")
        lines.append(f"  branches={sorted(current_branches)!r}")
        current_url = self._buildrequest_url(current_buildrequestid)
        if current_url:
            lines.append(f"  url={current_url}")
        lines.append("  sourcestamps:")
        for i, ss in enumerate(current_sourcestamps, 1):
            lines.append(f"    [{i}] {self._fmt_ss(ss)}")
        lines.append("")

        buildrequest_fields = [
            "buildrequestid",
            "buildsetid",
            "builderid",
            "claimed",
            "complete",
        ]
        filters = [
            Filter("complete", "eq", [False]),
            Filter("builderid", "eq", [current_builderid]),
        ]

        buildrequests = yield self.master.data.get(
            ("buildrequests",),
            filters=filters,
            fields=buildrequest_fields,
        )

        matches = yield self._find_pull_request_matches(
            [
                br
                for br in buildrequests
                if br["buildrequestid"] != current_buildrequestid
            ],
            current_targets,
            "incomplete",
        )

        if not matches:
            filters = [
                Filter("complete", "eq", [True]),
                Filter("builderid", "eq", [current_builderid]),
            ]
            buildrequests = yield self.master.data.get(
                ("buildrequests",),
                filters=filters,
                fields=buildrequest_fields,
                order=["-buildrequestid"],
                limit=self.recent_completed_limit,
            )
            matches = yield self._find_pull_request_matches(
                buildrequests,
                current_targets,
                "recent-completed",
            )

        actions = []
        for info in matches:
            brid = info["buildrequestid"]
            if self.dry_run:
                msg = (
                    f"[DRY-RUN] would stop current build "
                    f"because pull request buildrequest {brid} exists "
                    f"(source={info['source']}, "
                    f"claimed={info['claimed']}, "
                    f"revision={info['revision']!r}, "
                    f"branch={info['branch']!r})"
                )
            else:
                msg = (
                    f"Stopping current build because pull request buildrequest {brid} "
                    f"exists (source={info['source']}, "
                    f"claimed={info['claimed']}, "
                    f"revision={info['revision']!r}, "
                    f"branch={info['branch']!r})"
                )
            if info["url"]:
                msg += f" url={info['url']}"
            actions.append(msg)

        lines.append(f"Matched pull request buildrequests: {len(matches)}")
        lines.append("")

        if matches:
            lines.append("Matches:")
            for m in matches:
                lines.append(f"  - buildrequestid={m['buildrequestid']}")
                lines.append(f"    claimed={m['claimed']}")
                lines.append(f"    complete={m['complete']}")
                lines.append(f"    buildsetid={m['buildsetid']}")
                lines.append(f"    source={m['source']}")
                lines.append(f"    revision={m['revision']!r}")
                lines.append(f"    branch={m['branch']!r}")
                if m["url"]:
                    lines.append(f"    url={m['url']}")
            lines.append("")
            lines.append("Actions:")
            lines.extend(f"  {a}" for a in actions)
        else:
            lines.append(
                "No matching pull request buildrequests found on this builder."
            )

        self.addCompleteLog("duplicate-buildrequests", "\n".join(lines) + "\n")
        if matches and not self.dry_run:
            self.build.stopBuild("Superseded by pull request build for same commit")
            return CANCELLED
        return SUCCESS


# TODO: Upgrading buildbot to 4.* deprecates this class
# Use instead the OldBuildCanceller service
# https://docs.buildbot.net/latest/manual/configuration/services/old_build_canceller.html
class CancelOlderSameBranchRequests(BuildStep):
    name = "cancel older obsolete buildrequests"
    description = ["checking older matching requests"]
    descriptionDone = ["older matching requests checked"]

    def __init__(
        self,
        dry_run=False,
        same_builder_only=False,
        cancel_claimed=True,
        buildbot_base_url=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.dry_run = dry_run
        self.same_builder_only = same_builder_only
        self.cancel_claimed = cancel_claimed
        self.buildbot_base_url = (
            buildbot_base_url.rstrip("/") if buildbot_base_url else None
        )
        self._builder_name_cache = {}

    def _buildrequest_url(self, brid):
        if not self.buildbot_base_url:
            return None
        return f"{self.buildbot_base_url}/#/buildrequests/{brid}"

    @defer.inlineCallbacks
    def _builder_name(self, builderid):
        if builderid in self._builder_name_cache:
            return self._builder_name_cache[builderid]

        builder = yield self.master.data.get(("builders", builderid))
        name = builder.get("name", f"<builderid={builderid}>")
        self._builder_name_cache[builderid] = name
        return name

    @staticmethod
    def _fmt_ss(ss):
        return (
            f"branch={ss.get('branch')!r}, "
            f"repository={ss.get('repository')!r}, "
            f"revision={ss.get('revision')!r}, "
            f"codebase={ss.get('codebase', '')!r}"
        )

    @defer.inlineCallbacks
    def run(self):
        current_buildid = self.build.buildid

        current_build = yield self.master.data.get(("builds", current_buildid))
        current_buildrequestid = current_build["buildrequestid"]
        current_builderid = current_build["builderid"]
        current_buildername = yield self._builder_name(current_builderid)

        current_buildrequest = yield self.master.data.get(
            ("buildrequests", current_buildrequestid)
        )
        current_claimed_at = current_buildrequest.get("claimed_at")
        current_buildsetid = current_buildrequest["buildsetid"]

        current_buildset = yield self.master.data.get(("buildsets", current_buildsetid))
        current_submitted_at = current_buildset.get("submitted_at")
        current_sourcestamps = current_buildset.get("sourcestamps", [])

        if (
            current_claimed_at is None
            or current_submitted_at is None
            or not current_sourcestamps
        ):
            self.addCompleteLog(
                "summary",
                "Current buildrequest is missing claimed_at or current buildset "
                "is missing submitted_at or sourcestamps; nothing to do.\n",
            )
            return SUCCESS

        # We want only running or in queue buildrequests
        filters = [Filter("complete", "eq", [False])]
        # Narrow the search to cancel only buildrequests for the calling builder
        if self.same_builder_only:
            filters.append(Filter("builderid", "eq", [current_builderid]))

        # Getting all buildrequests based on filters
        buildrequests = yield self.master.data.get(
            ("buildrequests",),
            filters=filters,
            fields=[
                "buildrequestid",
                "buildsetid",
                "builderid",
                "claimed",
                "complete",
                "submitted_at",
            ],
        )

        # Log info about the current build
        lines = []
        lines.append(f"Mode: {'DRY-RUN' if self.dry_run else 'ACTIVE'}")
        lines.append(f"same_builder_only={self.same_builder_only}")
        lines.append(f"cancel_claimed={self.cancel_claimed}")
        lines.append("")
        lines.append("Current:")
        lines.append(f"  buildid={current_buildid}")
        lines.append(f"  buildrequestid={current_buildrequestid}")
        lines.append(f"  builderid={current_builderid}")
        lines.append(f"  buildername={current_buildername!r}")
        lines.append(f"  buildsetid={current_buildsetid}")
        lines.append(f"  claimed_at={current_claimed_at}")
        lines.append(f"  submitted_at={current_submitted_at}")
        current_url = self._buildrequest_url(current_buildrequestid)
        if current_url:
            lines.append(f"  url={current_url}")
        lines.append("  sourcestamps:")
        for i, ss in enumerate(current_sourcestamps, 1):
            lines.append(f"    [{i}] {self._fmt_ss(ss)}")
        lines.append("")

        matches = []
        actions = []
        cancel_errors = []

        for br in buildrequests:
            brid = br["buildrequestid"]

            # Skip self
            if brid == current_buildrequestid:
                continue

            # Skip cancelling running builds if cancel_claimed is False
            if not self.cancel_claimed and br.get("claimed"):
                continue

            other_buildsetid = br["buildsetid"]
            other_buildset = yield self.master.data.get(("buildsets", other_buildsetid))
            other_submitted_at = br.get("submitted_at")
            other_sourcestamps = other_buildset.get("sourcestamps", [])

            if other_submitted_at is None:
                continue

            # Newest wins: only cancel requests created before this request was claimed.
            if other_submitted_at >= current_claimed_at:
                continue

            # A match means same branch+repository+codebase but different revision
            matched_other_ss = None

            # If the buildset can have multiple sourcestamps
            for current_ss in current_sourcestamps:
                for other_ss in other_sourcestamps:
                    same_target = (
                        other_ss.get("codebase", "") == current_ss.get("codebase", "")
                        and other_ss.get("repository") == current_ss.get("repository")
                        and other_ss.get("branch") == current_ss.get("branch")
                    )
                    different_revision = other_ss.get("revision") != current_ss.get(
                        "revision"
                    )

                    if same_target and different_revision:
                        matched_other_ss = other_ss
                        break
                if matched_other_ss is not None:
                    break

            if matched_other_ss is None:
                continue

            other_builderid = br["builderid"]
            other_buildername = yield self._builder_name(other_builderid)

            info = {
                "buildrequestid": brid,
                "buildername": other_buildername,
                "claimed": br.get("claimed"),
                "complete": br.get("complete"),
                "submitted_at": other_submitted_at,
                "branch": matched_other_ss.get("branch"),
                "repository": matched_other_ss.get("repository"),
                "revision": matched_other_ss.get("revision"),
                "codebase": matched_other_ss.get("codebase", ""),
                "url": self._buildrequest_url(brid),
            }
            matches.append(info)

            # Dry-run mode doesn't actually cancel, just log what would be cancelled
            if self.dry_run:
                msg = (
                    f"[DRY-RUN] would cancel buildrequest {brid} "
                    f"(buildername={other_buildername!r}, "
                    f"claimed={br.get('claimed')}, "
                    f"submitted_at={other_submitted_at}, "
                    f"revision={matched_other_ss.get('revision')!r})"
                )
                if info["url"]:
                    msg += f" url={info['url']}"
                actions.append(msg)
            else:
                try:
                    yield self.master.data.control(
                        "cancel",
                        {"reason": ("Superseded by newer build for same branch")},
                        ("buildrequests", brid),
                    )
                except Exception as e:
                    msg = (
                        f"Failed to request cancel for buildrequest {brid} "
                        f"(buildername={other_buildername!r}, "
                        f"claimed={br.get('claimed')}, "
                        f"submitted_at={other_submitted_at}, "
                        f"revision={matched_other_ss.get('revision')!r}, "
                        f"error={e!r})"
                    )
                    if info["url"]:
                        msg += f" url={info['url']}"
                    actions.append(msg)
                    cancel_errors.append(msg)
                    log.err(e, f"Failed to request cancel for buildrequest {brid}")
                else:
                    msg = (
                        f"Requested cancel for buildrequest {brid} "
                        f"(buildername={other_buildername!r}, "
                        f"claimed={br.get('claimed')}, "
                        f"submitted_at={other_submitted_at}, "
                        f"revision={matched_other_ss.get('revision')!r})"
                    )
                    if info["url"]:
                        msg += f" url={info['url']}"
                    actions.append(msg)

        lines.append(f"Matched older buildrequests: {len(matches)}")
        lines.append(f"Cancel request failures: {len(cancel_errors)}")
        lines.append("")

        # Log detailed info about matched buildrequests and actions taken
        if matches:
            lines.append("Matches:")
            for m in matches:
                lines.append(f"  - buildrequestid={m['buildrequestid']}")
                lines.append(f"    buildername={m['buildername']!r}")
                lines.append(f"    claimed={m['claimed']}")
                lines.append(f"    complete={m['complete']}")
                lines.append(f"    submitted_at={m['submitted_at']}")
                lines.append(f"    branch={m['branch']!r}")
                lines.append(f"    repository={m['repository']!r}")
                lines.append(f"    revision={m['revision']!r}")
                lines.append(f"    codebase={m['codebase']!r}")
                if m["url"]:
                    lines.append(f"    url={m['url']}")
            lines.append("")
            lines.append("Actions:")
            lines.extend(f"  {a}" for a in actions)
        else:
            lines.append("No older matching buildrequests found.")

        self.addCompleteLog("obsolete-buildrequests", "\n".join(lines) + "\n")
        return SUCCESS
