from buildbot.plugins import util
from buildbot.www.authz.roles import RolesFromBase

# Who may force Foundry: MariaDB organization members, and of those only the
# listed usernames. GitHubAuth (API v3) doesn't report team membership.
#
# master-web's RolesFromGroups makes each of the user's GitHub organizations a
# role, so this one has a ":", which no organization or team name can: an
# organization can't be named into it.
FORCE_ROLE = "foundry:force"
FORCE_ORG = "MariaDB"


class _RolesFromListedMembers(RolesFromBase):
    # FORCE_ROLE for a user who is in usernames and in FORCE_ORG.
    def __init__(self, usernames: list[str]):
        super().__init__()
        self.usernames = usernames

    def getRolesFromUser(self, userDetails):
        if userDetails.get("username") in self.usernames and FORCE_ORG in (
            userDetails.get("groups") or []
        ):
            return [FORCE_ROLE]
        return []


def force_access(builder: str, usernames: list[str]):
    # master-web's role matchers and authz rules letting only those users
    # force builder. The rules go before its organization-wide rule; Rebuild
    # stays open. Apart from the builders, so tests can import it.
    role_matchers = [_RolesFromListedMembers(usernames)]
    rules = [
        util.ForceBuildEndpointMatcher(
            builder=builder, role=FORCE_ROLE, defaultDeny=True
        )
    ]
    return role_matchers, rules
