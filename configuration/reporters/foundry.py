from buildbot.plugins import reporters


class FoundryPullRequestStatusPush(reporters.GitHubStatusPush):
    # GitHubStatusPush for pull request builds only: force builds have no
    # revision to report on. Named, to tell it apart from master-web's.
    name = "FoundryPullRequestStatusPush"

    def filterBuilds(self, build):
        branch = build["properties"].get("branch", ("", None))[0] or ""
        return super().filterBuilds(build) and branch.startswith("refs/pull/")
