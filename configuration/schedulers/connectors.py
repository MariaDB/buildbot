import os
from functools import partial

import configuration.builders.definitions.connectors.conc as c_builders
import configuration.builders.definitions.connectors.concpp as cc_builders
import configuration.builders.definitions.connectors.conodbc as odbc_builders
from buildbot.plugins import schedulers, util
from configuration.schedulers.base import upstream_branch_fn

# Branches to monitor
ODBC_MAIN_BRANCHES = ["develop", "master", "odbc-3.1", "odbc-3.2"]
CPP_MAIN_BRANCHES = ["develop", "master", "cpp-1.0", "cpp-1.1"]
C_MAIN_BRANCHES = ["3.3", "3.4"]
TEST_BRANCHES = ["bb-*"]

# Repos to monitor
ODBC_REPO = os.environ.get("CONNECTOR_ODBC_REPO_URL")
CPP_REPO = os.environ.get("CONNECTOR_CPP_REPO_URL")
C_REPO = os.environ.get("CONNECTOR_C_REPO_URL")

CONODBC_SCHEDULERS = [
    schedulers.AnyBranchScheduler(
        name="conc_odbconc_c_upstream_scheduler",
        builderNames=[odbc_builders.TARBALL.name],
        treeStableTimer=60,
        change_filter=util.ChangeFilter(
            repository=ODBC_REPO,
            branch_fn=partial(
                upstream_branch_fn, filter_branches=ODBC_MAIN_BRANCHES + TEST_BRANCHES
            ),
        ),
    ),
    schedulers.Triggerable(
        name="conc_odbc_all_scheduler",
        builderNames=[
            builder.name
            for builder in odbc_builders.RPM_BUILDERS + odbc_builders.DEB_BUILDERS
        ],
    ),
]

CONCPP_SCHEDULERS = [
    schedulers.AnyBranchScheduler(
        name="conc_cpp_upstream_scheduler",
        builderNames=[cc_builders.TARBALL.name],
        treeStableTimer=60,
        change_filter=util.ChangeFilter(
            repository=CPP_REPO,
            branch_fn=partial(
                upstream_branch_fn, filter_branches=CPP_MAIN_BRANCHES + TEST_BRANCHES
            ),
        ),
    ),
    schedulers.Triggerable(
        name="conc_cpp_all_scheduler",
        builderNames=[
            builder.name
            for builder in cc_builders.RPM_BUILDERS + cc_builders.DEB_BUILDERS
        ],
    ),
]

CONC_SCHEDULERS = [
    schedulers.AnyBranchScheduler(
        name="conc_c_upstream_scheduler",
        builderNames=[c_builders.TARBALL.name],
        treeStableTimer=60,
        change_filter=util.ChangeFilter(
            repository=C_REPO,
            branch_fn=partial(
                upstream_branch_fn, filter_branches=C_MAIN_BRANCHES + TEST_BRANCHES
            ),
        ),
    ),
    schedulers.Triggerable(
        name="conc_c_all_scheduler",
        builderNames=[
            builder.name
            for builder in c_builders.RPM_BUILDERS + c_builders.DEB_BUILDERS
        ],
    ),
]
