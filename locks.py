import os

import yaml

from buildbot.plugins import util

# Local
from constants import builders_install, builders_upgrade, github_status_builders

LOCKS: dict[str, util.MasterLock] = {}
# worker_locks.yaml currently is in the same folder as locks.py.
# TODO: re-evaluate if this is the right place after multi-master
# is refactored to use a single base master.cfg.
with open(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "worker_locks.yaml"),
    encoding="utf-8",
) as file:
    locks = yaml.safe_load(file)
    for worker_name in locks:
        LOCKS[worker_name] = util.MasterLock(
            f"{worker_name}_lock", maxCount=locks[worker_name]
        )


@util.renderer
def getLocks(props):
    worker_name = props.getProperty("workername", default=None)
    builder_name = props.getProperty("buildername", default=None)
    assert worker_name is not None
    assert builder_name is not None

    if (
        builder_name in github_status_builders
        or builder_name in builders_install
        or builder_name in builders_upgrade
    ):
        return []

    if worker_name not in LOCKS:
        return []
    return [LOCKS[worker_name].access("counting")]
