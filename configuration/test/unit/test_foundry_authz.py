"""Only MariaDB members listed in force_users get the Foundry Force role,
whatever other GitHub groups a user has: master-web's RolesFromGroups turns
each into a role of the same name."""

import fnmatch
import re
import unittest

from buildbot.plugins import util
from configuration.schedulers.foundry_access import FORCE_ROLE, force_access

# A GitHub organization or user login. GitHubAuth's groups are these, or
# "<org>/<team>" when it reads team membership.
_GITHUB_LOGIN = r"[A-Za-z0-9](?:-?[A-Za-z0-9])*"


def _may_force(details, force_users):
    # As master-web/master.cfg puts them together.
    role_matchers, rules = force_access("foundry-trigger-builders", force_users)
    authz = util.Authz(
        allowRules=rules, roleMatchers=[util.RolesFromGroups()] + role_matchers
    )
    roles = authz.getRolesFromUser(details)
    return any(fnmatch.fnmatch(role, rules[0].role) for role in roles)


class TestFoundryForceRole(unittest.TestCase):
    def test_role_is_no_github_group(self):
        self.assertIsNone(re.fullmatch(_GITHUB_LOGIN, FORCE_ROLE))
        self.assertIsNone(re.fullmatch(f"{_GITHUB_LOGIN}/[a-z0-9_-]+", FORCE_ROLE))

    def test_allowlisted_member_may_force(self):
        details = {"username": "alice", "groups": ["MariaDB"]}
        self.assertTrue(_may_force(details, force_users=["alice"]))

    def test_allowlisted_user_outside_mariadb_may_not(self):
        for groups in [[], ["foundry-force"], ["MariaDB-fork"]]:
            with self.subTest(groups=groups):
                details = {"username": "alice", "groups": groups}
                self.assertFalse(_may_force(details, force_users=["alice"]))

    def test_groups_alone_never_grant_force(self):
        # e.g. an organization named like the old role, "foundry-force".
        for group in ["MariaDB", "foundry-force", "foundry", "foundry/force"]:
            with self.subTest(group=group):
                details = {"username": "mallory", "groups": [group]}
                self.assertFalse(_may_force(details, force_users=["alice"]))


if __name__ == "__main__":
    unittest.main()
