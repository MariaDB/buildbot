from buildbot.plugins import *
from buildbot.process.properties import Property, Properties
from buildbot.steps.shell import ShellCommand, Compile, Test, SetPropertyFromCommand
from buildbot.steps.mtrlogobserver import MTR, MtrLogObserver
from buildbot.steps.source.github import GitHub
from buildbot.process.remotecommand import RemoteCommand
from twisted.internet import defer

from constants import *

####### LOCKS
#main_master_lock = util.MasterLock('main_master_lock', maxCount=30)

hz_bbw1_lock = util.MasterLock('hz_bbw1_lock', maxCount=9)
hz_bbw2_lock = util.MasterLock('hz_bbw2_lock', maxCount=1)
hz_bbw4_lock = util.MasterLock('hz_bbw4_lock', maxCount=9)
hz_bbw5_lock = util.MasterLock('hz_bbw5_lock', maxCount=9)
amd_bbw1_lock = util.MasterLock('amd_bbw1_lock', maxCount=6)
amd_bbw2_lock = util.MasterLock('amd_bbw2_lock', maxCount=8)
intel_bbw1_lock = util.MasterLock('intel_bbw1_lock', maxCount=7)
p9_rhel8_bbw1_lock = util.MasterLock('p9_rhel8_bbw1_lock', maxCount=9)
p9_rhel7_bbw1_lock = util.MasterLock('p9_rhel7_bbw1_lock', maxCount=6)
p9_db_bbw1_lock = util.MasterLock('p9_db_bbw1_lock', maxCount=12)
aarch_bbw1_lock = util.MasterLock('aarch64_bbw1_lock', maxCount=2)
aarch_bbw2_lock = util.MasterLock('aarch64_bbw2_lock', maxCount=2)
aarch_bbw3_lock = util.MasterLock('aarch64_bbw3_lock', maxCount=2)
aarch_bbw4_lock = util.MasterLock('aarch64_bbw4_lock', maxCount=2)
aarch_bbw5_lock = util.MasterLock('aarch64_bbw5_lock', maxCount=15)
aarch_bbw6_lock = util.MasterLock('aarch64_bbw6_lock', maxCount=15)
aarch_bbw7_lock = util.MasterLock('aarch64_bbw7_lock', maxCount=15)
apexis_bbw1_lock = util.MasterLock('apexis_bbw1_lock', maxCount=1)
apexis_bbw2_lock = util.MasterLock('apexis_bbw2_lock', maxCount=1)
bg_bbw1_lock = util.MasterLock('bg_bbw1_lock', maxCount=3)
bg_bbw2_lock = util.MasterLock('bg_bbw2_lock', maxCount=2)
bg_bbw3_lock = util.MasterLock('bg_bbw3_lock', maxCount=2)
bg_bbw4_lock = util.MasterLock('bg_bbw4_lock', maxCount=2)
win_bbw1_lock = util.MasterLock('win_bbw1_lock', maxCount=1)
win_bbw2_lock = util.MasterLock('win_bbw2_lock', maxCount=4)
s390x_bbw1_lock = util.MasterLock('s390x_bbw1_lock', maxCount=3)
s390x_bbw2_lock = util.MasterLock('s390x_bbw2_lock', maxCount=3)
s390x_bbw3_lock = util.MasterLock('s390x_bbw3_lock', maxCount=3)

@util.renderer
def getLocks(props):
    worker_name = props.getProperty('workername', default=None)
    builder_name = props.getProperty('buildername', default=None)
    assert worker_name is not None
    assert builder_name is not None

    if builder_name in github_status_builders or builder_name in builders_install or builder_name in builders_upgrade:
        return []
    locks = []
    #else:
    #    locks = [main_master_lock.access('counting')]

    if 'hz-bbw1-docker' in worker_name:
        locks = locks + [hz_bbw1_lock.access('counting')]
    if 'hz-bbw2-docker' in worker_name:
        locks = locks + [hz_bbw2_lock.access('counting')]
    if 'hz-bbw4-docker' in worker_name:
        locks = locks + [hz_bbw4_lock.access('counting')]
    if 'hz-bbw5-docker' in worker_name:
        locks = locks + [hz_bbw5_lock.access('counting')]
    if 'intel-bbw1-docker' in worker_name:
        locks = locks + [intel_bbw1_lock.access('counting')]
    if 'ppc64le-rhel8-bbw1-docker' in worker_name:
        locks = locks + [p9_rhel8_bbw1_lock.access('counting')]
    if 'ppc64le-rhel7-bbw1-docker' in worker_name:
        locks = locks + [p9_rhel7_bbw1_lock.access('counting')]
    if 'ppc64le-db-bbw1-docker' in worker_name:
        locks = locks + [p9_db_bbw1_lock.access('counting')]
    if 'aarch64-bbw1-docker' in worker_name:
        locks = locks + [aarch_bbw1_lock.access('counting')]
    if 'aarch64-bbw2-docker' in worker_name:
        locks = locks + [aarch_bbw2_lock.access('counting')]
    if 'aarch64-bbw3-docker' in worker_name:
        locks = locks + [aarch_bbw3_lock.access('counting')]
    if 'aarch64-bbw4-docker' in worker_name:
        locks = locks + [aarch_bbw4_lock.access('counting')]
    if 'aarch64-bbw5-docker' in worker_name:
        locks = locks + [aarch_bbw5_lock.access('counting')]
    if 'aarch64-bbw6-docker' in worker_name:
        locks = locks + [aarch_bbw6_lock.access('counting')]
    if 'aarch64-bbw7-docker' in worker_name:
        locks = locks + [aarch_bbw7_lock.access('counting')]
    if 'fjord1-docker' in worker_name:
        locks = locks + [apexis_bbw1_lock.access('counting')]
    if 'fjord2-docker' in worker_name:
        locks = locks + [apexis_bbw2_lock.access('counting')]
    if 'ns-x64-bbw1-docker' in worker_name:
        locks = locks + [bg_bbw1_lock.access('counting')]
    if 'ns-x64--bbw2-docker' in worker_name:
        locks = locks + [bg_bbw2_lock.access('counting')]
    if 'ns-x64--bbw3-docker' in worker_name:
        locks = locks + [bg_bbw3_lock.access('counting')]
    if 'ns-x64-bbw4-docker' in worker_name:
        locks = locks + [bg_bbw4_lock.access('counting')]
    if 'bbw1-docker-windows' in worker_name:
        locks = locks + [win_bbw1_lock.access('counting')]
    if 'bbw2-docker-windows' in worker_name:
        locks = locks + [win_bbw2_lock.access('counting')]
    if 's390x-bbw1-docker' in worker_name:
        locks = locks + [s390x_bbw1_lock.access('counting')]
    if 's390x-bbw2-docker' in worker_name:
        locks = locks + [s390x_bbw2_lock.access('counting')]
    if 's390x-bbw3-docker' in worker_name:
        locks = locks + [s390x_bbw3_lock.access('counting')]
    if 'amd-bbw1-docker' in worker_name:
        locks = locks + [amd_bbw1_lock.access('counting')]
    if 'amd-bbw2-docker' in worker_name:
        locks = locks + [amd_bbw2_lock.access('counting')]

    return locks

