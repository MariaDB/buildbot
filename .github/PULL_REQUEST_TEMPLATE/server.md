# Server builders

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- On buildbot.dev.mariadb.org: which builders ran, with links to their builds. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes
- [ ] The number of autogen masters is unchanged, if `os_info.yaml` changed (see `docs/server-builders.md`)

<!-- Keep the sections below that apply, and delete the others. -->

### Adding a release platform

- [ ] Build image added to the workflow of its family, with `nogalera: true` until Galera packages exist for it
- [ ] `-srpm` image added to `build-srpm.yml`, if master-migration or the Connectors build rpm packages for it
- [ ] libvirt VMs deployed on the dev hosts (sysadmin repository on [git.mariadb.org](https://git.mariadb.org))
- [ ] libvirt VMs deployed on the production hosts, before this is merged to `main`
- [ ] Entry in `os_info.yaml`
- [ ] `<arch>-<os>` in `SUPPORTED_PLATFORMS` for every version it supports
- [ ] Galera, S3 or SSL suites, if wanted: `BUILDERS_GALERA_MTR`, `BUILDERS_S3_MTR`, `BUILDERS_SSL_MTR`
- [ ] Install and upgrade scripts in `scripts/` handle the distribution, and were tested on dev: they are live on production once merged to `main`
- [ ] Front page updated: `master-web/templates/home.jade`
- [ ] The Connectors and Foundry build for it too, or a follow-up is planned
- [ ] [Platform deprecation policy](https://mariadb.com/docs/release-notes/community-server/about/platform-deprecation-policy) page updated
- [ ] After the first Galera build for it on `mariadb-4.x`: image rebuilt with Galera

### Removing a platform

- [ ] Removed from `os_info.yaml`
- [ ] Removed from `SUPPORTED_PLATFORMS`, `GITHUB_STATUS_BUILDERS` and the `BUILDERS_*_MTR` lists in `constants.py`
- [ ] Other builders that use its image removed or moved: searched `master-*/` and `configuration/` (Connectors, Foundry) for its image tag
- [ ] If one of its builders is a required check on GitHub: the branch protection rules change when this is deployed, or pull requests wait for that check forever
- [ ] Its images removed from the image workflows (`build-*.yml`, `build-srpm.yml`)
- [ ] Front page updated: `master-web/templates/home.jade`
- [ ] Platform deprecation policy page updated
- [ ] libvirt VMs removed from the hosts, once this is deployed on both environments

### Adding a server version

- [ ] Branch in `BRANCHES_MAIN`
- [ ] `SUPPORTED_PLATFORMS[<version>]`, usually a copy of the previous version's
- [ ] `DEVELOPMENT_BRANCH`, if the upgrade tests should treat it as not GA yet
- [ ] Branch links on the home page and the grid view: `master-web/templates/home.jade`, `master-web/templates/grid_view/grid.jade`
- [ ] Foundry builds for it: `MARIADB_VERSIONS` in `configuration/builders/definitions/foundry/settings.py`

### Removing a server version

- [ ] Removed from `BRANCHES_MAIN`
- [ ] Removed from `SUPPORTED_PLATFORMS`. The later versions' lists are copied from earlier ones: if this one is their base, the base list moves to the next version
- [ ] Conditions on this version removed: searched factories, `master.cfg` files and `scripts/` for it
- [ ] Branch links removed from the home page and the grid view
- [ ] Removed from Foundry's `MARIADB_VERSIONS`

### Adding or changing a builder

- [ ] A new builder is on master-migration
- [ ] Its `jobs` fit its workers' `total_jobs` (the bbm-deploy check's summary)
- [ ] In `SUPPORTED_PLATFORMS` for the versions it should build
- [ ] To report to GitHub: in `GITHUB_STATUS_BUILDERS`, and fast enough for pull requests. To be a required check, it is added to the branch protection rules by the repository's admins
- [ ] Tested on dev, with the triggers limited to this builder

### Removing a builder

- [ ] Removed from `SUPPORTED_PLATFORMS` and `GITHUB_STATUS_BUILDERS`, and from the branch protection rules if it was a required check
- [ ] The workers and images that only it used removed

### Install and upgrade tests (master-libvirt)

- [ ] A VM exists, on the dev and the production hosts, for every install builder added
- [ ] Changes to `scripts/` tested on dev: they are live on production as soon as they are merged to `main`
