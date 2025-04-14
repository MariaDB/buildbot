import fnmatch
import os
import re
from datetime import datetime
from typing import Any, Tuple

import docker
from pyzabbix import ZabbixAPI

from buildbot.buildrequest import BuildRequest
from buildbot.interfaces import IProperties
from buildbot.master import BuildMaster
from buildbot.plugins import steps, util, worker
from buildbot.process.builder import Builder
from buildbot.process.buildstep import BuildStep
from buildbot.process.results import FAILURE
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from buildbot.worker import AbstractWorker
from constants import (
    ALL_BB_TEST_BRANCHES,
    BUILDERS_AUTOBAKE,
    BUILDERS_BIG,
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


def getScript(scriptname: str) -> steps.ShellCommand:
    branch = os.environ["BRANCH"]
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
    if "vladbogo" in dockerfile or "quay" in dockerfile:
        dockerfile_str = None
        image_str = dockerfile
        need_pull = True
    else:
        dockerfile_str = open("dockerfiles/" + dockerfile).read()
        image_str = None
        need_pull = False

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
        properties={"jobs": jobs, "save_packages": save_packages},
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
    worker: AbstractWorker = wfb.worker
    if "s390x" not in worker.name:
        return True

    worker_prefix = "-".join(worker.name.split("-")[0:2])
    worker_name = private_config["private"]["worker_name_mapping"][worker_prefix]
    # TODO(cvicentiu) this could be done with a yield to not have the master
    # stuck until the network operation is completed.
    load = getMetric(worker_name, "BB_accept_new_build")

    if float(load) > 60:
        worker.quarantine_timeout = 60
        worker.putInQuarantine()
        return False

    worker.quarantine_timeout = 120
    worker.putInQuarantine()
    worker.resetQuarantine()
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


@util.renderer
def dockerfile(props: IProperties) -> str:
    worker = props.getProperty("workername")
    return (
        "https://github.com/MariaDB/buildbot/tree/main/dockerfiles/"
        + "-".join(worker.split("-")[-2:])
        + ".dockerfile"
    )


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
    if fnmatch.fnmatch(branch, "10.[56]"):
        dockerbase = "ubuntu-2004-deb-autobake"
    elif fnmatch.fnmatch(branch, "10.11"):
        dockerbase = "ubuntu-2204-deb-autobake"
    else:
        dockerbase = "ubuntu-2404-deb-autobake"

    # UBI images
    if branch != "10.5" and builder_name.endswith("amd64-rhel-9-rpm-autobake"):
        return True

    # We only build on the above autobakes for all architectures
    return builder_name.endswith(dockerbase)


def filterBranch(step: BuildStep) -> str:
    if "10.5" in step.getProperty("branch"):
        return False
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


def hasBigtest(step: BuildStep) -> bool:
    builder_name = step.getProperty("buildername")
    for b in BUILDERS_BIG:
        if builder_name in b:
            return True
    return False


def hasRpmLint(step: BuildStep) -> str:
    builder_name = step.getProperty("buildername")
    # The step fails on s390x SLES 12 due to permissions issues
    if "s390x-sles-12" in builder_name:
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


# Zabbix helper
def getMetric(hostname: str, metric: str) -> Any:
    # set API
    zapi = ZabbixAPI(private_config["private"]["zabbix_server"])
    zapi.session.verify = True
    zapi.timeout = 10

    zapi.login(api_token=private_config["private"]["zabbix_token"])

    host_id = None
    for h in zapi.host.get(output="extend"):
        if h["host"] == hostname:
            host_id = h["hostid"]
            break

    assert host_id is not None

    hostitems = zapi.item.get(filter={"hostid": host_id, "name": metric})

    assert len(hostitems) == 1
    hostitem = hostitems[0]

    last_value = hostitem["lastvalue"]
    last_time = datetime.fromtimestamp(int(hostitem["lastclock"]))

    elapsed_from_last = (datetime.now() - last_time).total_seconds()

    # The latest data is no older than 80 seconds
    assert elapsed_from_last < 80

    return last_value


def read_template(template_name: str) -> str:
    with open(f"/srv/buildbot/master/script_templates/{template_name}.sh") as f:
        return f.read()


def isJepsenBranch(step: BuildStep) -> bool:
    return step.getProperty("branch").startswith("jpsn")


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
