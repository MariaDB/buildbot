from twisted.internet import defer

from buildbot.plugins import *
from buildbot.process import results
from buildbot.process.properties import Properties, Property
from buildbot.process.remotecommand import RemoteCommand
from buildbot.steps.mtrlogobserver import MTR, MtrLogObserver
from buildbot.steps.package.rpm.rpmlint import RpmLint
from buildbot.steps.shell import Compile, SetPropertyFromCommand, ShellCommand, Test
from buildbot.steps.source.github import GitHub
from constants import *
from utils import *


# TODO for FetchTestData/getLastNFailedBuildsFactory
#
# * do something about skips (makes little sense to run N failed tests if
#   they're all skipped)
# * the way SELECT works it looks for {limit} unique test names within last
#   {limit*scale} failures. Better to make buildbot to autotune the scale.
#   The smaller it is, the faster will the query run (but it's <1s already)
# * uses N=50 now, this could be increased to catch more failures or decreased
#   to run faster
# * more branch protection builders should use it
# * run for view protocol and sanitizers
# * how to do it for install/upgrade tests?
#
class FetchTestData(MTR):
    def __init__(self, mtrDbPool, test_type, **kwargs):
        self.mtrDbPool = mtrDbPool
        self.test_type = test_type
        super().__init__(dbpool=mtrDbPool, **kwargs)

    @defer.inlineCallbacks
    def get_tests_for_type(self, branch, typ, limit):
        scale = 20
        query = f"""
            select concat(test_name, ',', test_variant)
            from
              (select id, test_name, test_variant
               from test_failure join test_run on (test_run_id=id)
               where branch='{branch}' and typ='{typ}'
               order by test_run_id desc limit {limit*scale}) x
            group by test_name, test_variant
            order by max(id) desc limit {limit}
        """
        tests = yield self.runQueryWithRetry(query)
        return list(t[0] for t in tests)

    @defer.inlineCallbacks
    def run(self):
        test_re = r"^(?:.+/)?mysql-test/(?:suite/)?(.+?)/(?:[rt]/)?([^/]+)\.(?:test|result|rdiff)$"
        branch = self.getProperty("master_branch")
        limit = 50

        if branch:
            tests = yield self.get_tests_for_type(branch, self.test_type, limit)
            if len(tests) < limit:
                # if there're not enough failures for the given test_type
                # bump it up with the failures for the default type.
                # "mtr" is what buildbot uses when test_type wasn't set
                tests += yield self.get_tests_for_type(
                    branch, "mtr", limit - len(tests)
                )

            tests += (
                m.expand(r"\1.\2")
                for m in (re.search(test_re, f) for f in self.build.allFiles())
                if m
            )

            if tests:
                test_args = " ".join(set(tests))
                self.setProperty("tests_to_run", test_args)

        return results.SUCCESS


def addPostTests(factory):
    factory.addStep(saveLogs())

    ## trigger packages
    factory.addStep(
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
    factory.addStep(
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
    factory.addStep(
        steps.SetPropertyFromCommand(
            command="basename mariadb-*-linux-*.tar.gz",
            property="mariadb_binary",
            doStepIf=savePackage,
        )
    )
    factory.addStep(
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
    factory.addStep(
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
    factory.addStep(
        steps.ShellCommand(
            name="cleanup", command="rm -r * .* 2> /dev/null || true", alwaysRun=True
        )
    )
    return factory


def getBuildFactoryPreTest(build_type="RelWithDebInfo", additional_args=""):
    f_quick_build = util.BuildFactory()
    f_quick_build.addStep(printEnv())
    f_quick_build.addStep(
        steps.SetProperty(
            property="dockerfile",
            value=util.Interpolate("%(kw:url)s", url=dockerfile),
            description="dockerfile",
        )
    )
    f_quick_build.addStep(getSourceTarball())
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
    # build steps
    f_quick_build.addStep(
        steps.Compile(
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    "cmake . -DCMAKE_BUILD_TYPE=%(kw:build_type)s -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER=%(kw:c_compiler)s -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER=%(kw:cxx_compiler)s -DPLUGIN_TOKUDB=NO -DPLUGIN_MROONGA=NO -DPLUGIN_SPIDER=YES -DPLUGIN_OQGRAPH=NO -DPLUGIN_PERFSCHEMA=%(kw:perf_schema)s -DPLUGIN_SPHINX=NO %(kw:additional_args)s && make %(kw:verbose_build)s -j%(kw:jobs)s %(kw:create_package)s",
                    perf_schema=util.Property("perf_schema", default="YES"),
                    build_type=util.Property("build_type", default=f"{build_type}"),
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                    c_compiler=util.Property("c_compiler", default="gcc"),
                    cxx_compiler=util.Property("cxx_compiler", default="g++"),
                    additional_args=util.Property(
                        "additional_args", default=f"{additional_args}"
                    ),
                    create_package=util.Property("create_package", default="package"),
                    verbose_build=util.Property("verbose_build", default=""),
                ),
            ],
            env={"CCACHE_DIR": "/mnt/ccache"},
            haltOnFailure="true",
        )
    )
    return f_quick_build


def addTests(factory, test_type, mtrDbPool, mtrArgs):
    factory.addStep(
        steps.MTR(
            name=f"{test_type} test",
            logfiles={"mysqld*": "./buildbot/mysql_logs.html"},
            test_type=test_type,
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    rf"""
            cd mysql-test &&
            exec perl mysql-test-run.pl {test_type_to_mtr_arg[test_type]} --verbose-restart --force --retry=3 --max-save-core=2 --max-save-datadir=10 --max-test-fail=20 --mem --parallel=$(expr %(kw:jobs)s \* 2) %(kw:mtr_additional_args)s
            """,
                    mtr_additional_args=mtrArgs,
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
            timeout=950,
            haltOnFailure="true",
            parallel=mtrJobsMultiplier,
            dbpool=mtrDbPool,
            autoCreateTables=True,
            env=MTR_ENV,
        )
    )
    factory.addStep(
        steps.ShellCommand(
            name=f"move {test_type} mariadb log files",
            alwaysRun=True,
            command=[
                "bash",
                "-c",
                util.Interpolate(
                    moveMTRLogs(output_dir=test_type),
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN"),
                ),
            ],
        )
    )
    factory.addStep(
        steps.ShellCommand(
            name=f"create {test_type} var archive",
            alwaysRun=True,
            command=["bash", "-c", util.Interpolate(createVar(output_dir=test_type))],
            doStepIf=hasFailed,
        )
    )
    return factory


def addGaleraTests(factory, mtrDbPool):
    factory.addStep(
        steps.MTR(
            description="testing galera",
            descriptionDone="test galera",
            logfiles={"mysqld*": "./buildbot/mysql_logs.html"},
            test_type="nm",
            command=[
                "sh",
                "-c",
                util.Interpolate(
                    r"""
           cd mysql-test &&
           if [ -f "$WSREP_PROVIDER" ]; then exec perl mysql-test-run.pl --verbose-restart --force --retry=3 --max-save-core=2 --max-save-datadir=10 --max-test-fail=20 --mem --big-test --parallel=$(expr %(kw:jobs)s \* 2) %(kw:mtr_additional_args)s --suite=wsrep,galera,galera_3nodes,galera_3nodes_sr; fi
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
    factory.addStep(
        steps.ShellCommand(
            name="move mariadb galera log files",
            alwaysRun=True,
            command=[
                "bash",
                "-c",
                util.Interpolate(
                    "mv ./buildbot/logs ./buildbot/logs_main\n"
                    + moveMTRLogs()
                    + "\nmv ./buildbot/logs ./buildbot/logs_galera; mv ./buildbot/logs_main ./buildbot/logs; mv ./buildbot/logs_galera ./buildbot/logs/galera\n",
                    jobs=util.Property("jobs", default="$(getconf _NPROCESSORS_ONLN)"),
                ),
            ],
            doStepIf=hasGalera,
        )
    )
    return factory


def getQuickBuildFactory(test_type, mtrDbPool):
    f = getBuildFactoryPreTest()
    addTests(f, test_type, mtrDbPool, util.Property("mtr_additional_args", default=""))
    addGaleraTests(f, mtrDbPool)
    return addPostTests(f)


def getLastNFailedBuildsFactory(test_type, mtrDbPool):
    @util.renderer
    def getTests(props):
        mtr_additional_args = props.getProperty("mtr_additional_args", "--suite=main")
        tests_to_run = props.getProperty("tests_to_run", None)
        if tests_to_run:
            mtr_additional_args = re.sub(
                r"--suite=\S*", "--skip-not-found " + tests_to_run, mtr_additional_args
            )

        return mtr_additional_args

    config = {
        "nm": {
            "args": ("RelWithDebInfo", "-DWITH_EMBEDDED_SERVER=ON"),
            "steps": ("nm", "ps", "emb", "emb-ps"),  # TODO "view"
        },
        "debug": {
            "args": ("Debug", "-DWITH_EMBEDDED_SERVER=ON"),
            "steps": ("debug", "debug-ps", "debug-emb", "debug-emb-ps"),  # TODO "view"
        },
    }

    f = getBuildFactoryPreTest(*config[test_type]["args"])

    for typ in config[test_type]["steps"]:
        f.addStep(
            FetchTestData(
                name=f"Get last N failed {typ} tests",
                mtrDbPool=mtrDbPool,
                test_type=typ,
            )
        )
        addTests(f, typ, mtrDbPool, getTests)

    return addPostTests(f)


def getRpmAutobakeFactory(mtrDbPool):
    ## f_rpm_autobake
    f_rpm_autobake = util.BuildFactory()
    f_rpm_autobake.addStep(printEnv())
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
    f_rpm_autobake.addStep(getSourceTarball())
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
    f_rpm_autobake.addStep(steps.RpmLint(doStepIf=hasRpmLint))
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
            if [ "%(prop:rpm_type)s" = rhel8 ] || [ "%(prop:rpm_type)s" = centosstream8 ] || [ "%(prop:rpm_type)s" = alma8 ] || [ "%(prop:rpm_type)s" = rocky8 ]; then
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
