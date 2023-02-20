from buildbot.plugins import *
from buildbot.process.properties import Property, Properties
from buildbot.process.results import FAILURE
from buildbot.steps.shell import ShellCommand, Compile, Test, SetPropertyFromCommand
from buildbot.steps.mtrlogobserver import MTR, MtrLogObserver
from buildbot.steps.source.github import GitHub
from buildbot.process.remotecommand import RemoteCommand
from twisted.internet import defer
import re
import sys
import docker
from datetime import timedelta, datetime

from pyzabbix import ZabbixAPI

from constants import *

private_config = { "private": {} }
exec(open("/srv/buildbot/master/master-private.cfg").read(), private_config, { })

def envFromProperties(envlist):
    d = dict()
    for e in envlist:
        d[e] = util.Interpolate(f'%(prop:{e})s')
    d['tarbuildnum'] = util.Interpolate("%(prop:tarbuildnum)s")
    d['development_branch']= DEVELOPMENT_BRANCH
    return d

def getScript(scriptname):
    return steps.ShellCommand(
      name=f"fetch_{scriptname}",
      command=["bash", "-xc", f"""
  for script in bash_lib.sh {scriptname}; do
    [[ ! -f $script ]] && wget "https://raw.githubusercontent.com/MariaDB/buildbot/main/scripts/$script"
  done
  chmod a+x {scriptname}
"""])

# BUILD HELPERS

# Helper function that creates a worker instance.
def createWorker(worker_name_prefix, worker_id, worker_type, dockerfile, jobs=5,
                 save_packages=False, shm_size='15G', worker_name_suffix='',
                 volumes=['/srv/buildbot/ccache:/mnt/ccache',
                          '/srv/buildbot/packages:/mnt/packages',
                          '/mnt/autofs/master_packages/:/packages']):
    worker_name = worker_name_prefix + str(worker_id) + '-docker'
    name = worker_name + worker_type

    i = worker_id
    tls = None

    if worker_name_prefix.startswith('hz'):
        b_name = 'x64-bbw'
    elif worker_name_prefix.startswith('intel'):
        b_name = 'x64-bbw'
    elif worker_name_prefix.startswith('ppc64le'):
        b_name = 'ppc64le-bbw'
    elif worker_name_prefix.startswith('amd'):
        b_name = 'x64-bbw'
    else:
        b_name = worker_name_prefix
    base_name = b_name + '-docker' + worker_type

    # Set master FQDN - default to wireguard interface
    fqdn = '100.64.100.1'
    if re.match('aarch64-bbw[1-4]', worker_name):
        fqdn = 'buildbot.mariadb.org'
    if 'vladbogo' in dockerfile or 'quay' in dockerfile:
        dockerfile_str = None
        image_str = dockerfile
        need_pull = True
    else:
        dockerfile_str = open("dockerfiles/" + dockerfile).read()
        image_str = None
        need_pull = False
    if 'rhel' in worker_type and dockerfile_str is not None and not 'download' in dockerfile:
        dockerfile_str = dockerfile_str % (private_config["private"]["rhel_sub"]["user"], config["private"]["rhel_sub"]["password"])
    worker_instance = worker.DockerLatentWorker(name + worker_name_suffix, None,
                        docker_host=private_config["private"]["docker_workers"][worker_name],
                        image=image_str,
                        dockerfile=dockerfile_str,
                        tls=tls,
                        autopull=True,
                        alwaysPull=need_pull,
                        followStartupLogs=False,
                        masterFQDN=fqdn,
                        build_wait_timeout=0,
                        missing_timeout=600,
                        max_builds=1,
                        hostconfig={'shm_size':shm_size, 'ulimits': [docker.types.Ulimit(name='memlock', soft=51200000, hard=51200000)]},
                        volumes=volumes,
                        properties={ 'jobs':jobs, 'save_packages':save_packages })
    return ((base_name, name + worker_name_suffix), worker_instance)

def downloadSourceTarball():
    return ShellCommand(
             name="fetch_tarball",
             description="fetching source tarball",
             descriptionDone="fetching source tarball...done",
             haltOnFailure=True,
             command=["bash", "-xc", util.Interpolate("""
    d=/mnt/packages/
    f="%(prop:tarbuildnum)s_%(prop:mariadb_version)s.tar.gz"
    find $d -type f -mtime +2 -delete -ls

    # Do not use flock for AIX
    os=$(uname -s)
    use_flock=""
    if [[ $os != "AIX" ]]; then
      use_flock="flock \"$d$f\" "
    fi
    cmd="$use_flock wget -cO \"$d$f\" \"https://ci.mariadb.org/%(prop:tarbuildnum)s/%(prop:mariadb_version)s.tar.gz\""

    res=1
    for i in {1..10}; do
      if eval "$cmd"; then
        res=0
        break
      else
        sleep "$i"
      fi
    done
    if ((res != 0)); then
      exit $res
    fi
""")])

# git branch filter using fnmatch
import fnmatch
def staging_branch_fn(branch):
    return fnmatch.fnmatch(branch, 'prot-st-*')
def fnmatch_any(s, list_of_patterns):
    return any(fnmatch.fnmatch(s, p) for p in list_of_patterns)

# Priority filter based on saved package branches
def nextBuild(bldr, requests):
    for r in requests:
        if fnmatch_any(r.sources[""].branch, releaseBranches):
            return r
    for r in requests:
        if fnmatch_any(r.sources[""].branch, savedPackageBranches):
            return r
    return requests[0]

@defer.inlineCallbacks
def shell(command, worker, builder):
    args = {
        'command': command,
        'logEnviron': False,
        'workdir': "/srv/buildbot/worker",
        'want_stdout': False,
        'want_stderr': False,
    }
    cmd = RemoteCommand('shell', args, stdioLogName=None)
    cmd.worker = worker
    yield cmd.run(FakeStep(), worker.conn, builder.name)
    return cmd.rc

def canStartBuild(builder, wfb, request):
    worker=wfb.worker
    if not "s390x" in worker.name:
        return True

    worker_prefix = "-".join((worker.name).split('-')[0:2])
    worker_name = private_config["private"]["worker_name_mapping"][worker_prefix]
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
def mtrJobsMultiplier(props):
    jobs = props.getProperty('jobs', default=20)
    return jobs * 2

# ls2string gets the output of ls and returns a space delimited string with the files and directories
def ls2string(rc, stdout, stderr):
    lsFilenames = []

    for l in stdout.strip().split('\n'):
        if l != "":
            lsFilenames.append(l.strip())

    return { 'packages' : " ".join(lsFilenames) }

# ls2list gets the output of ls and returns a list with the files and directories
def ls2list(rc, stdout, stderr):
    lsFilenames = []

    for l in stdout.strip().split('\n'):
        if l != "":
            lsFilenames.append(l.strip())

    return { 'packages' : lsFilenames }

# Save packages for current branch?
def savePackage(step, savedBranches=savedPackageBranches):
    builderName = str(step.getProperty("buildername"))

    # Debug builders do not create the bintar, so there are no packages to save
    if 'debug' in builderName:
      return False

    return step.getProperty("save_packages") and \
           fnmatch_any(step.getProperty("branch"), savedBranches)

# Return a HTML file that contains links to MTR logs
def getHTMLLogString():
    return """
echo '<!DOCTYPE html>
<html>
<body>' >> /buildbot/mysql_logs.html

echo '<a href="https://ci.mariadb.org/%(prop:tarbuildnum)s/logs/%(prop:buildername)s/">mysqld* log dir</a><br>' >> /buildbot/mysql_logs.html
echo '<a href="https://ci.mariadb.org/%(prop:tarbuildnum)s/logs/%(prop:buildername)s/var.tar.gz">var.tar.gz</a><br>' >> /buildbot/mysql_logs.html

echo '</body>
</html>' >> /buildbot/mysql_logs.html"""

def hasFailed(step):
    return step.build.results == FAILURE

def createVar():
    return """
if [ -d mysql-test/var ]; then
    extra=
    if [ -f  ./mysql-test/var/log/*/mysqld.*/data/core*gz ]; then
      if [ -f sql/mysqld ]; then extra=sql/mysqld; fi
      if [ -f sql/mariadbd ]; then extra=sql/mariadbd; fi
      extra=mysql-test/var/[0-9]*/{mysqld.[0-9],my.cnf}
    fi
    tar zcf var.tar.gz mysql-test/var/*/log mysql-test/var/log ${extra}
    mv var.tar.gz /buildbot/logs/
fi
"""

# Function to move the MTR logs to a known location so that they can be saved
def moveMTRLogs():
    return """
echo Logs available at https://ci.mariadb.org/%(prop:tarbuildnum)s/logs/%(prop:buildername)s/

mkdir -p /buildbot/logs

filename="mysql-test/var/log/mysqld.1.err"
if [ -f $filename ]; then
   cp $filename /buildbot/logs/mysqld.1.err
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
       cp $filename /buildbot/logs/$logname
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
done
"""

@util.renderer
def dockerfile(props):
    worker = props.getProperty('workername')
    return "https://github.com/MariaDB/buildbot/tree/main/dockerfiles/" + "-".join(worker.split('-')[-2:]) + '.dockerfile'

# checks if the list of files is empty
def hasFiles(step):
  if len(step.getProperty("packages")) < 1:
    return False
  else:
    return True

def hasInstall(props):
    builderName = str(props.getProperty("buildername"))

    for b in builders_install:
        if builderName in b:
            return True
    return False

def hasUpgrade(props):
    builderName = str(props.getProperty("buildername"))

    for b in builders_upgrade:
        if builderName in b:
            return True
    return False

def hasEco(props):
    builderName = str(props.getProperty("buildername"))

    for b in builders_eco:
        if builderName in b:
            return True
    return False

def hasCompat(step):
    builderName = str(step.getProperty("buildername"))

    # For s390x there are no compat files
    if 's390x' in builderName:
        return False
    if 'rhel' in builderName or 'centos' in builderName:
        return step.getProperty('rpm_type')[-1] in ['7', '8']
    if 'fedora' in builderName:
        return step.getProperty('rpm_type')[-1] in ['35', '36']
    return True

@util.renderer
def getDockerLibraryNames(props):
    return builders_dockerlibrary[0]

@util.renderer
def getWordpressNames(props):
    return builders_wordpress[0]

def hasDockerLibrary(step):
    # Can only build with a saved package
    if not savePackage(step):
        return False

    branch = str(step.getProperty("master_branch"))
    builderName = str(step.getProperty("buildername"))

    # from https://github.com/MariaDB/mariadb-docker/blob/next/update.sh#L7-L15
    if fnmatch.fnmatch(branch, '10.2'):
        dockerbase = "ubuntu-1804-deb-autobake"
    elif fnmatch.fnmatch(branch, '10.[3-7]'):
        dockerbase = "ubuntu-2004-deb-autobake"
    else:
        dockerbase = "ubuntu-2204-deb-autobake"

    # We only build on the above autobakes for all architectures
    return builderName.endswith(dockerbase)

def filterBranch(step):
  if '10.5' in step.getProperty("branch"):
        return False
  if '10.6' in step.getProperty("branch"):
        return False
  return True

# check if branch is a staging branch
def isStagingBranch(step):
  if staging_branch_fn(step.getProperty("branch")):
    return True
  else:
    return False

# returns true if build is succeeding
def ifStagingSucceeding(step):
  if isStagingBranch(step):
    step.setProperty("build_results", step.build.results)
    return step.build.results in ('SUCCESS', 'WARNINGS')
  else:
    return False

# set step's waitForFinish to True if staging branch
def waitIfStaging(step):
  if isStagingBranch(step):
    step.waitForFinish = True
  return True

def hasAutobake(props):
    builderName = props.getProperty("buildername")
    for b in builders_autobake:
        if builderName in b:
            return True
    return False

def hasBigtest(props):
    builderName = str(props.getProperty("buildername"))

    for b in builders_big:
        if builderName in b:
            return True
    return False

@util.renderer
def getArch(props):
    buildername = props.getProperty('buildername')
    return buildername.split('-')[0]

####### SCHEDULER HELPER FUNCTIONS
@util.renderer
def getBranchBuilderNames(props):
    mBranch = props.getProperty("master_branch")

    builders = list(filter(
        lambda x: x not in github_status_builders,
        supportedPlatforms[mBranch]))

    return builders

@util.renderer
def getProtectedBuilderNames(props):
    mBranch = props.getProperty("master_branch")

    builders = list(filter(
        lambda x: x in supportedPlatforms[mBranch],
        github_status_builders))

    return builders

@util.renderer
def getAutobakeBuilderNames(props):
    builderName = props.getProperty("parentbuildername")
    for b in builders_autobake:
        if builderName in b:
            return [b]
    return []

@util.renderer
def getBigtestBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    for b in builders_big:
        if builderName in b:
            return [b]
    return []

@util.renderer
def getInstallBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    for b in builders_install:
        if builderName in b:
            return [b]
    return []

@util.renderer
def getUpgradeBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    builds = []
    for b in builders_upgrade:
        if builderName in b:
            builds.append(b)
    return builds

@util.renderer
def getEcoBuilderNames(props):
    builderName = str(props.getProperty("parentbuildername"))

    builds = []
    for b in builders_eco:
        if builderName in b:
            builds.append(b)
    return builds

##### Builder priority
# Prioritize builders. At this point, only the Windows builders need a higher priority
# since the others run on dedicated machines.
def prioritizeBuilders(buildmaster, builders):
    """amd64-windows-* builders should have the highest priority since they are used for
    protected branches"""
    builderPriorities = {
        "amd64-windows": 0,
        "amd64-windows-packages": 1,
    }
    builders.sort(key=lambda b: builderPriorities.get(b.name, 2))
    return builders

##### Zabbix helper
def getMetric(hostname, metric):
    # set API
    zapi = ZabbixAPI(private_config["private"]["zabbix_server"])

    zapi.session.verify = True

    zapi.timeout = 10

    zapi.login(api_token=private_config["private"]["zabbix_token"])

    host_id = None
    for h in zapi.host.get(output="extend"):
        if h['host'] == hostname:
            host_id = h['hostid']
            break

    assert host_id is not None

    hostitems = zapi.item.get(filter={"hostid": host_id, "name": metric})

    assert len(hostitems) == 1
    hostitem = hostitems[0]

    last_value = hostitem['lastvalue']
    last_time = datetime.fromtimestamp(int(hostitem['lastclock']))

    elapsed_from_last = (datetime.now() - last_time).total_seconds()

    # The latest data is no older than 80 seconds
    assert elapsed_from_last < 80

    return last_value
