import os

import yaml

from buildbot.plugins import util

# Local
from constants import (
    BUILDERS_INSTALL,
    BUILDERS_UPGRADE,
    GITHUB_STATUS_BUILDERS,
    RELEASE_BRANCHES,
)
from utils import fnmatch_any

LOCKS: dict[str, util.MasterLock] = {}
# worker_locks.yaml currently is in the same folder as locks.py.
# TODO: re-evaluate if this is the right place after multi-master
# is refactored to use a single base master.cfg.
with open(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "worker_locks.yaml"),
    encoding="utf-8",
) as file:
    locks = yaml.safe_load(file)
    for worker_base_name in locks:
        LOCKS[worker_base_name] = util.MasterLock(
            f"{worker_base_name}_lock", maxCount=locks[worker_base_name]
        )


@util.renderer
def getLocks(props):
    worker_name = props.getProperty("workername", default=None)
    builder_name = props.getProperty("buildername", default=None)
    branch = props.getProperty("branch", default=None)
    assert worker_name is not None
    assert builder_name is not None

    if (
        builder_name in GITHUB_STATUS_BUILDERS
        or builder_name in BUILDERS_INSTALL
        or builder_name in BUILDERS_UPGRADE
    ):
        return []

    # Autobake (packages) builders on release branches disobey locks
    if (
        branch
        and "autobake" in builder_name.lower()
        and fnmatch_any(branch, RELEASE_BRANCHES)
    ):
        return []

    for worker_base_name in LOCKS:
        if worker_name.startswith(worker_base_name):
            return [LOCKS[worker_base_name].access("counting")]
    return []
