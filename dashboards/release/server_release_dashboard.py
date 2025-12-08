import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import requests
from flask import Flask, render_template, request

from constants import SUPPORTED_PLATFORMS

INSTANCE = "https://buildbot.mariadb.org"
BUILDBOT_API_URL = f"{INSTANCE}/api/v2"
JIRA_API_URL = "https://jira.mariadb.org/rest/api/2"
CACHE_DURATION = (
    10 * 60
)  # Cache the rendered page for 10 minutes to avoid excessive API calls


@dataclass(frozen=True)
class Severity:
    css_color_class: str
    symbol: str
    releasability: str


class Severities:
    OK = Severity("success", "✓", "Releaseable")
    WARN = Severity("warning", "⚠", "Needs Attention")
    BAD = Severity("danger", "✖", "Not Releaseable")
    PENDING = Severity("pending", "🕒", "Pending")


@dataclass
class Builder:
    builder_name: str
    builder_id: int
    tags: list[str]


@dataclass
class Build:
    build_id: int
    build_number: int
    builder_id: int
    results: str
    _status: Severity = None

    @property
    def status(self):
        if self._status:
            return self._status
        if self.results == "build successful":
            return Severities.OK
        elif self.results.lower() in [
            "acquiring locks",
            "building",
            "preparing worker",
        ]:
            return Severities.PENDING
        else:
            return Severities.BAD

    @status.setter
    def status(self, value: Severities):
        self._status = value


@dataclass
class ReleaseSeriesBuild:
    build_number: int
    builder_name: str
    builder_id: int
    result: str
    build: Build = None

    @property
    def url(self):
        if self.build_number is None:
            return f"{INSTANCE}/#/builders/{self.builder_id}/"
        return f"{INSTANCE}/#/builders/{self.builder_id}/builds/{self.build_number}"


@dataclass
class Release:
    version: str
    released: bool
    release_planned_date: date
    release_start_date: date
    description: str
    builders: dict[Severities, list[ReleaseSeriesBuild]] = field(
        default_factory=lambda: defaultdict(list)
    )
    commit: str = None
    jira: int = None

    @property
    def series(self):
        return ".".join(self.version.split(".")[:2])

    @property
    def branch(self):
        return f"bb-{self.series}-release"

    @property
    def status(self):
        if Severities.BAD in self.builders:
            return Severities.BAD
        elif Severities.WARN in self.builders:
            return Severities.WARN
        elif not self.builders or Severities.PENDING in self.builders:
            return Severities.PENDING
        else:
            return Severities.OK

    @property
    def mariadb_version(self):
        return f"mariadb-{self.version}"


class Dashboard:
    def __init__(self, supported_platforms: dict):
        self._next_releases = []
        self._tarball_docker_builder_id = None
        self._supported_platforms = supported_platforms

    def _set_next_releases(self):
        """
        Sets the next planned releases from JIRA.
        """
        releases = self._get_releases_from_jira()
        self._next_releases = self._get_next_planned_releases(releases)

    def _get_releases_from_jira(self):
        """
        Gets all releases from JIRA for the MDEV project, unfiltered.
        """
        url = f"{JIRA_API_URL}/project/MDEV/versions"
        response = requests.get(url)
        response.raise_for_status()
        return [
            Release(
                version=r["name"],
                released=r["released"],
                release_planned_date=(
                    date.fromisoformat(r["releaseDate"])
                    if r.get("releaseDate")
                    else None
                ),
                release_start_date=(
                    date.fromisoformat(r["startDate"]) if r.get("startDate") else None
                ),
                description=r.get("description", ""),
                jira=r["id"],
            )
            for r in response.json()
        ]

    def _get_next_planned_releases(self, releases):
        """
        From a list of releases, get the next planned release for each series.
        """
        next_planned = {}
        for r in releases:
            if not r.released and r.release_planned_date:
                # pick the earliest planned release for each series
                # sometimes more than one future release is planned in JIRA for the same series
                if (
                    r.series not in next_planned
                    or r.release_planned_date
                    < next_planned[r.series].release_planned_date
                ):
                    next_planned[r.series] = r

        return next_planned.values()

    def _get_release_builders(self):
        """
        Get all builders from Buildbot that are tagged with 'release_packages' and map them to their series.
        Also capture the builder ID for 'tarball-docker' builder, later used to get the mariadb_version property from its builds.
        """
        url = f"{BUILDBOT_API_URL}/builders"
        response = requests.get(url)
        data = response.json()
        builders = {}
        for b in data.get("builders", []):
            if b.get("name") == "tarball-docker":
                self._tarball_docker_builder_id = b.get("builderid")
            for series, platforms in self._supported_platforms.items():
                if (
                    "release_packages" in b.get("tags", [])
                    and b.get("name")
                    .removesuffix("-rpm-autobake")
                    .removesuffix("-deb-autobake")
                    in platforms
                ):
                    if series not in builders:
                        builders[series] = []
                    builders[series].append(
                        Builder(
                            builder_name=b.get("name"),
                            builder_id=b.get("builderid"),
                            tags=b.get("tags", []),
                        )
                    )
        return builders

    def _get_latest_builds_per_branch(self, branch):
        """
        For a given branch, usually bb-<series>-release, get the latest builds for the most recent change on that branch
        """
        url = f"{BUILDBOT_API_URL}/changes?branch={branch}&limit=1&order=-changeid"
        response = requests.get(url)
        data = response.json()

        changes = data.get("changes", [])
        if not changes:
            return {}, ""

        commit = changes[0].get("revision", "")
        builds = changes[0].get("builds", [])
        if not builds:
            return {}, ""

        latest_run_by_builder = {}
        for b in builds:
            builder_id = b.get("builderid")
            started_at = b.get("started_at", 0)

            # Re-runs appear as separate builds, for the same builder, under the same change.
            if builder_id not in latest_run_by_builder:
                latest_run_by_builder[builder_id] = b
            else:
                if started_at > latest_run_by_builder[builder_id].get("started_at", 0):
                    latest_run_by_builder[builder_id] = b

        result = {}
        for builder_id, b in latest_run_by_builder.items():
            result[builder_id] = Build(
                build_id=b.get("id"),
                build_number=b.get("number"),
                builder_id=builder_id,
                results=b.get("state_string"),
            )

        return result, commit

    def _get_mariadb_version(self, build_id):
        """
        MariaDB version is stored as a build property 'mariadb_version'.
        Originally from the source VERSION file.
        """

        def get_build_details(build_id):
            url = f"{BUILDBOT_API_URL}/builds/{build_id}?property=mariadb_version"
            response = requests.get(url)
            data = response.json()
            return data

        build_details = get_build_details(build_id)
        for build_info in build_details.get("builds", []):
            properties = build_info.get("properties", {})
            mariadb_version = properties.get("mariadb_version", [])
            if mariadb_version:
                return str(mariadb_version[0])
        return None

    def render_releases(self):
        self._set_next_releases()
        builders = self._get_release_builders()

        if not self._tarball_docker_builder_id or not self._next_releases:
            return []  # Cannot proceed without tarball-docker builder or next releases

        for release in self._next_releases:
            # Release Branch is a bb-<series>-release branch. We get the latest builds from the latest change on that branch
            builds, commit = self._get_latest_builds_per_branch(release.branch)
            series_builders = builders.get(release.series, [])

            # If we have a tarball-docker build there's a chance we have other builds too
            if self._tarball_docker_builder_id in builds:
                mariadb_version = self._get_mariadb_version(
                    builds[self._tarball_docker_builder_id].build_id
                )
                # We make sure we only pick changes that correspond to this release version i.e. mariadb-<version>
                # because usually bb-<series>-release branches are reused for multiple releases in the same series
                if release.mariadb_version == mariadb_version:
                    release.commit = commit  # Set the commit only after we've confirmed it is the right changeset
                    for builder in series_builders:
                        if builder.builder_id in builds:
                            build = builds[builder.builder_id]

                            # Builders that are not producing packages are most probably failed at tests
                            # so we downgrade their status from BAD to WARN but they will mark the release as needing attention
                            if (
                                "autobake" not in builder.tags
                                and build.status == Severities.BAD
                            ):
                                build.status = Severities.WARN

                            release.builders[build.status].append(
                                ReleaseSeriesBuild(
                                    build_number=build.build_number,
                                    builder_name=builder.builder_name,
                                    builder_id=builder.builder_id,
                                    result=build.results,
                                    build=build,
                                )
                            )
                        else:
                            # If no build was found, most likely has not started yet
                            # so the release status will be pending
                            release.builders[Severities.PENDING].append(
                                ReleaseSeriesBuild(
                                    build_number=None,
                                    builder_name=builder.builder_name,
                                    builder_id=builder.builder_id,
                                    result="No build available",
                                    build=None,
                                )
                            )
        return self._next_releases, self.generated_at

    @property
    def generated_at(self):
        return datetime.now(tz=timezone.utc)


class ReleaseDashboard:
    def __init__(self):
        self.flask_app = Flask("test", root_path=os.path.dirname(__file__))
        self.cache = None

        self.flask_app.jinja_env.add_extension("jinja2.ext.loopcontrols")

        @self.flask_app.route("/")
        @self.flask_app.route("/index.html")
        def main():
            force_refresh = request.args.get("refresh", "").lower() in {
                "1",
                "yes",
                "true",
            }

            if self.cache is not None and not force_refresh:
                result, deadline = self.cache
                if time.monotonic() <= deadline:
                    return result

            result = self.get_release_status()
            deadline = time.monotonic() + CACHE_DURATION
            self.cache = (result, deadline)
            return result

    def get_release_status(self):
        state, generated_at = Dashboard(SUPPORTED_PLATFORMS).render_releases()

        if not state:
            return "No upcoming releases found."

        return render_template(
            "release.html",
            state=state,
            Severities=Severities,
            generated_at=generated_at,
        )


def get_release_status_app(buildernames=None, **kwargs):
    return ReleaseDashboard(**kwargs).flask_app
