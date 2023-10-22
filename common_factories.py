from buildbot.plugins import *
from buildbot.process import results
from buildbot.process.properties import Property, Properties
from buildbot.steps.package.rpm.rpmlint import RpmLint
from buildbot.steps.shell import ShellCommand, Compile, Test, SetPropertyFromCommand
from buildbot.steps.mtrlogobserver import MTR, MtrLogObserver
from buildbot.steps.source.github import GitHub
from buildbot.process.remotecommand import RemoteCommand
from twisted.internet import defer

from utils import *
from constants import *

class FetchTestData(MTR):
    def __init__(self, mtrDbPool, **kwargs):
        self.mtrDbPool = mtrDbPool
        super().__init__(dbpool=mtrDbPool, **kwargs)

    @defer.inlineCallbacks
    def run(self):
        master_branch = self.getProperty('master_branch')
        typ = 'nm'
        limit = 50
        overlimit = 1000
        test_re = r'^(?:.+/)?mysql-test/(?:suite/)?(.+?)/(?:[rt]/)?([^/]+)\.(?:test|result|rdiff)$'

        if master_branch:
            query = """
            select concat(test_name,',',test_variant) from (select id, test_name,test_variant from test_failure,test_run where branch='%s' and test_run_id=id order by test_run_id desc limit %d) x group by test_name,test_variant order by max(id) desc limit %d
            """
            tests = yield self.runQueryWithRetry(query % (master_branch, overlimit, limit))
            tests = list(t[0] for t in tests)

            tests += (m.expand(r'\1.\2') for m in (re.search(test_re, f) for f in self.build.allFiles()) if m)

            if tests:
                test_args = ' '.join(tests)
                self.setProperty('tests_to_run', test_args)

        return results.SUCCESS

def getBaseBuildFactory(mtrDbPool, mtrArgs):
    f_quick_build = util.BuildFactory()
    f_quick_build.addStep(
        steps.ShellCommand(
            name="Environment details",
            command=["bash", "-c", "date -u && uname -a && ulimit -a"],
        )
    )
    f_quick_build.addStep(
        steps.SetProperty(
            property="dockerfile",
            value=util.Interpolate("%(kw:url)s", url=dockerfile),
            description="dockerfile",
        )
    )
    f_quick_build.addStep(downloadSourceTarball())
    f_quick_build.addStep(
        steps.ShellCommand(
            command=util.Interpolate(
                "tar -xvzf /mnt/packages/%(prop:tarbuildnum)s_%(prop:mariadb_version)s.tar.gz --strip-components=1"
            )
        )
    )
    f_quick_build.addStep(
        steps.ShellCommand(
            name="create html log file",
            command=[
                "bash",
                "-c",
                util.Interpolate(
                    getHTMLLogString(),
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
        )
    )
    f_quick_build.addStep(FetchTestData(name="Get last N failed tests", mtrDbPool=mtrDbPool))
    # build steps
    f_quick_build.addStep(
        steps.Compile(
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    "cmake . -DCMAKE_BUILD_TYPE=%(kw:build_type)s -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER=%(kw:c_compiler)s -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER=%(kw:cxx_compiler)s -DPLUGIN_TOKUDB=NO -DPLUGIN_MROONGA=NO -DPLUGIN_SPIDER=YES -DPLUGIN_OQGRAPH=NO -DPLUGIN_PERFSCHEMA=%(kw:perf_schema)s -DPLUGIN_SPHINX=NO %(kw:additional_args)s && make %(kw:verbose_build)s -j%(kw:jobs)s %(kw:create_package)s",
                    perf_schema=util.Property("perf_schema", default="YES"),
                    build_type=util.Property("build_type", default="RelWithDebInfo"),
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                    c_compiler=util.Property("c_compiler", default="gcc"),
                    cxx_compiler=util.Property("cxx_compiler", default="g++"),
                    additional_args=util.Property("additional_args", default=""),
                    create_package=util.Property("create_package", default="package"),
                    verbose_build=util.Property("verbose_build", default=""),
                ),
            ],
            env={"CCACHE_DIR": "/mnt/ccache"},
            haltOnFailure="true",
        )
    )
    f_quick_build.addStep(
        steps.MTR(
            logfiles={"mysqld*": "/buildbot/mysql_logs.html"},
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    """
            cd mysql-test &&
            exec perl mysql-test-run.pl --verbose-restart --force --retry=3 --max-save-core=1 --max-save-datadir=10 --max-test-fail=20 --mem --parallel=$(expr %(kw:jobs)s \* 2) %(kw:mtr_additional_args)s
            """, mtr_additional_args=mtrArgs,
            jobs=util.Property('jobs', default='$(getconf _NPROCESSORS_ONLN)'),
        )],
        timeout=950,
        haltOnFailure="true",
        parallel=mtrJobsMultiplier,
        dbpool=mtrDbPool,
        autoCreateTables=True,
        env=MTR_ENV,
    ))
    f_quick_build.addStep(steps.ShellCommand(name="move mariadb log files", alwaysRun=True, command=['bash', '-c', util.Interpolate(moveMTRLogs(), jobs=util.Property('jobs', default='$(getconf _NPROCESSORS_ONLN'))]))
    f_quick_build.addStep(steps.ShellCommand(name="create var archive", alwaysRun=True, command=['bash', '-c', util.Interpolate(createVar())], doStepIf=hasFailed))
    f_quick_build.addStep(steps.MTR(
        description="testing galera",
        descriptionDone="test galera",
        logfiles={"mysqld*": "/buildbot/mysql_logs.html"},
        command=["sh", "-c", util.Interpolate("""
           cd mysql-test &&
           if [ -f "$WSREP_PROVIDER" ]; then exec perl mysql-test-run.pl --verbose-restart --force --retry=3 --max-save-core=1 --max-save-datadir=10 --max-test-fail=20 --mem --big-test --parallel=$(expr %(kw:jobs)s \* 2) %(kw:mtr_additional_args)s --suite=wsrep,galera,galera_3nodes,galera_3nodes_sr; fi
           """,
                    mtr_additional_args=util.Property(
                        "mtr_additional_args", default=""
                    ),
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
            timeout=950,
            haltOnFailure="true",
            parallel=mtrJobsMultiplier,
            dbpool=mtrDbPool,
            autoCreateTables=True,
            env=MTR_ENV,
            doStepIf=hasGalera,
        )
    )
    f_quick_build.addStep(
        steps.ShellCommand(
            name="move mariadb galera log files",
            alwaysRun=True,
            command=[
                "bash",
                "-c",
                util.Interpolate(
                    "mv /buildbot/logs /buildbot/logs_main\n"
                    + moveMTRLogs()
                    + "\nmv /buildbot/logs /buildbot/logs_galera; mv /buildbot/logs_main /buildbot/logs; mv /buildbot/logs_galera /buildbot/logs/galera\n",
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
            doStepIf=hasGalera,
        )
    )
    f_quick_build.addStep(
        steps.DirectoryUpload(
            name="save log files",
            compress="bz2",
            alwaysRun=True,
            workersrc="/buildbot/logs/",
            masterdest=util.Interpolate(
                "/srv/buildbot/packages/"
                + "%(prop:tarbuildnum)s"
                + "/logs/"
                + "%(prop:buildername)s"
            ),
        )
    )

    ## trigger packages
    f_quick_build.addStep(
        steps.Trigger(
            schedulerNames=["s_packages"],
            waitForFinish=False,
            updateSourceStamp=False,
            alwaysRun=True,
            set_properties={
                "parentbuildername": Property("buildername"),
                "tarbuildnum": Property("tarbuildnum"),
                "mariadb_version": Property("mariadb_version"),
                "master_branch": Property("master_branch"),
            },
            doStepIf=hasAutobake,
        )
    )
    ## trigger bigtest
    f_quick_build.addStep(
        steps.Trigger(
            schedulerNames=["s_bigtest"],
            waitForFinish=False,
            updateSourceStamp=False,
            set_properties={
                "parentbuildername": Property("buildername"),
                "tarbuildnum": Property("tarbuildnum"),
                "mariadb_version": Property("mariadb_version"),
                "master_branch": Property("master_branch"),
            },
            doStepIf=hasBigtest,
        )
    )
    # create package and upload to master
    f_quick_build.addStep(
        steps.SetPropertyFromCommand(
            command="basename mariadb-*-linux-*.tar.gz",
            property="mariadb_binary",
            doStepIf=savePackage,
        )
    )
    f_quick_build.addStep(
        steps.ShellCommand(
            name="save_packages",
            timeout=7200,
            haltOnFailure=True,
            command=util.Interpolate(
                """
        mkdir -p /packages/%(prop:tarbuildnum)s/%(prop:buildername)s \
        && sha256sum %(prop:mariadb_binary)s >> sha256sums.txt \
        && cp %(prop:mariadb_binary)s sha256sums.txt /packages/%(prop:tarbuildnum)s/%(prop:buildername)s/ \
        && sync /packages/%(prop:tarbuildnum)s
        """
            ),
            doStepIf=savePackage,
        )
    )
    f_quick_build.addStep(
        steps.Trigger(
            name="eco",
            schedulerNames=["s_eco"],
            waitForFinish=False,
            updateSourceStamp=False,
            set_properties={
                "parentbuildername": Property("buildername"),
                "tarbuildnum": Property("tarbuildnum"),
                "mariadb_binary": Property("mariadb_binary"),
                "mariadb_version": Property("mariadb_version"),
                "master_branch": Property("master_branch"),
                "parentbuildername": Property("buildername"),
            },
            doStepIf=lambda step: savePackage(step) and hasEco(step),
        )
    )
    f_quick_build.addStep(
        steps.ShellCommand(
            name="cleanup", command="rm -r * .* 2> /dev/null || true", alwaysRun=True
        )
    )
    return f_quick_build

def getQuickBuildFactory(mtrDbPool):
    return getBaseBuildFactory(mtrDbPool,util.Property(
                        "mtr_additional_args", default=""
                    ))

def getLastNFailedBuildFactory(mtrDbPool):
    @util.renderer
    def getTests(props):
        mtr_additional_args = props.getProperty('mtr_additional_args', '--suite=main')
        tests_to_run = props.getProperty('tests_to_run', None)
        if tests_to_run:
            mtr_additional_args = mtr_additional_args.replace('--suite=main', tests_to_run)

        return mtr_additional_args

    return getBaseBuildFactory(mtrDbPool, getTests)

def getRpmAutobakeFactory(mtrDbPool):
    ## f_rpm_autobake
    f_rpm_autobake = util.BuildFactory()
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            name="Environment details",
            command=["bash", "-c", "date -u && uname -a && ulimit -a"],
        )
    )
    f_rpm_autobake.addStep(
        steps.SetProperty(
            property="dockerfile",
            value=util.Interpolate("%(kw:url)s", url=dockerfile),
            description="dockerfile",
        )
    )
    f_rpm_autobake.workdir = (
        f_rpm_autobake.workdir + "/padding_for_CPACK_RPM_BUILD_SOURCE_DIRS_PREFIX/"
    )
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            name="fetch packages for MariaDB-compat",
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    'wget --no-check-certificate -cO ../MariaDB-shared-5.3.%(kw:arch)s.rpm "%(kw:url)s/helper_files/mariadb-shared-5.3-%(kw:arch)s.rpm" && wget -cO ../MariaDB-shared-10.1.%(kw:arch)s.rpm "%(kw:url)s/helper_files/mariadb-shared-10.1-kvm-rpm-%(kw:rpm_type)s-%(kw:arch)s.rpm"',
                    arch=getArch,
                    url=os.getenv("ARTIFACTS_URL", default="https://ci.mariadb.org"),
                    rpm_type=util.Property("rpm_type"),
                ),
            ],
            doStepIf=hasCompat,
        )
    )
    f_rpm_autobake.addStep(downloadSourceTarball())
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            command=util.Interpolate(
                "tar -xvzf /mnt/packages/%(prop:tarbuildnum)s_%(prop:mariadb_version)s.tar.gz --strip-components=1"
            )
        )
    )
    f_rpm_autobake.addStep(steps.ShellCommand(command="ls .."))
    # build steps
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            logfiles={"CMakeCache.txt": "CMakeCache.txt"},
            name="cmake",
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    "export PATH=/usr/lib/ccache:/usr/lib64/ccache:$PATH && cmake . -DBUILD_CONFIG=mysql_release -DRPM=%(kw:rpm_type)s -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache  %(kw:mtr_additional_args)s",
                    mtr_additional_args=util.Property(
                        "mtr_additional_args", default=""
                    ),
                    rpm_type=util.Property("rpm_type"),
                ),
            ],
            env={"CCACHE_DIR": "/mnt/ccache"},
            description="cmake",
        )
    )
    f_rpm_autobake.addStep(steps.RpmLint())
    f_rpm_autobake.addStep(
        steps.Compile(
            command=[
                "sh",
                "-xc",
                util.Interpolate(
                    """
            mkdir -p rpms srpms
            if grep -qw CPACK_RPM_SOURCE_PKG_BUILD_PARAMS CPackSourceConfig.cmake; then
                make package_source
                mv *.src.rpm srpms/
            fi
            export PATH=/usr/lib/ccache:/usr/lib64/ccache:$PATH && make -j %(kw:jobs)s package
        """,
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
            env={"CCACHE_DIR": "/mnt/ccache"},
            description="make package",
        )
    )
    # list rpm contents
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            command=[
                "sh",
                "-c",
                'for rpm in *.rpm; do echo $rpm ; rpm -q --qf "[%{FILEMODES:perms} %{FILEUSERNAME} %{FILEGROUPNAME} .%-36{FILENAMES}\n]" $rpm; echo "------------------------------------------------"; done',
            ],
            description="list rpm contents",
        )
    )
    # upload binaries
    f_rpm_autobake.addStep(
        steps.SetPropertyFromCommand(command="ls -1 *.rpm", extract_fn=ls2string)
    )
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            command=[
                "bash",
                "-xc",
                util.Interpolate(
                    """
            if [ -e MariaDB-shared-10.1.*.rpm ]; then
               rm MariaDB-shared-10.1.*.rpm
            fi
            mv *.rpm rpms/
            createrepo rpms/
            cat << EOF > MariaDB.repo
[MariaDB-%(prop:branch)s]
name=MariaDB %(prop:branch)s repo (build %(prop:tarbuildnum)s)
baseurl=%(kw:url)s/%(prop:tarbuildnum)s/%(prop:buildername)s/rpms
gpgcheck=0
EOF
            if [ "%(prop:rpm_type)s" = rhel8 ] || [ "%(prop:rpm_type)s" = centosstream8 ]; then
                echo "module_hotfixes = 1" >> MariaDB.repo
            fi
        """,
                    url=os.getenv("ARTIFACTS_URL", default="https://ci.mariadb.org"),
                ),
            ]
        )
    )
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            name="save_packages",
            timeout=7200,
            haltOnFailure=True,
            command=util.Interpolate(
                """
                mkdir -p /packages/%(prop:tarbuildnum)s/%(prop:buildername)s &&
                cp -r MariaDB.repo rpms srpms /packages/%(prop:tarbuildnum)s/%(prop:buildername)s/ &&
                ln -sf %(prop:tarbuildnum)s/%(prop:buildername)s/MariaDB.repo /packages/%(prop:branch)s-latest-%(prop:buildername)s.repo &&
                sync /packages/%(prop:tarbuildnum)s
"""
            ),
            doStepIf=lambda step: hasFiles(step) and savePackage(step),
            descriptionDone=util.Interpolate(
                """
Repository available with: curl %(kw:url)s/%(prop:tarbuildnum)s/%(prop:buildername)s/MariaDB.repo -o /etc/yum.repos.d/MariaDB.repo""",
                url=os.getenv("ARTIFACTS_URL", default="https://ci.mariadb.org"),
            ),
        )
    )
    f_rpm_autobake.addStep(
        steps.Trigger(
            name="install",
            schedulerNames=["s_install"],
            waitForFinish=False,
            updateSourceStamp=False,
            set_properties={
                "tarbuildnum": Property("tarbuildnum"),
                "mariadb_version": Property("mariadb_version"),
                "master_branch": Property("master_branch"),
                "parentbuildername": Property("buildername"),
            },
            doStepIf=lambda step: hasInstall(step)
            and savePackage(step)
            and hasFiles(step),
        )
    )
    f_rpm_autobake.addStep(
        steps.Trigger(
            name="major-minor-upgrade",
            schedulerNames=["s_upgrade"],
            waitForFinish=False,
            updateSourceStamp=False,
            set_properties={
                "tarbuildnum": Property("tarbuildnum"),
                "mariadb_version": Property("mariadb_version"),
                "master_branch": Property("master_branch"),
                "parentbuildername": Property("buildername"),
            },
            doStepIf=lambda step: hasUpgrade(step)
            and savePackage(step)
            and hasFiles(step),
        )
    )
    f_rpm_autobake.addStep(
        steps.ShellCommand(
            name="cleanup", command="rm -r * .* 2> /dev/null || true", alwaysRun=True
        )
    )
    return f_rpm_autobake
