# Foundry build pipeline

Builds each plugin of [MariaDB/foundry](https://github.com/MariaDB/foundry) (one per top-level directory, built with `cmake -P run.cmake`) as a native package for every supported MariaDB version, OS and architecture, then installs it and runs its MTR suites.

## Pipeline

1. **Trigger**: Force, or a GitHub pull request on Foundry.
1. **Dispatch** (`foundry-trigger-builders`): clones Foundry, finds the plugins to build and publishes a `git archive` of the commit. This is the run's only clone from GitHub.
1. **Fan out**: one `Triggerable` per MariaDB version, carrying the archive, the plugins and the server package source.
1. **Build and test**, per OS and architecture, from the archive. rpm/deb packages are built in the worker image, then installed and tested in the plain upstream `base_image`, so an undeclared dependency fails. Bintar targets build against a server bintar and test inside it.
1. **Report**: the dispatcher fails if any package build does. On a pull request, that is its GitHub status.

## Starting a run

**Force**, open to the MariaDB organization members listed in `FORCE_USERS` in `settings.py` (other MariaDB members can still Rebuild):

- an optional Foundry commit (full SHA), else the tip of `main`;
- per MariaDB version: the MariaDB Server mirrors (default), a ci.mariadb.org `tarbuildnum`, or skip. A version not on the mirrors yet offers only a `tarbuildnum` or skip, and defaults to skip.

**Pull request**: builds only the plugins it changes (all of them if it changes `CMakeLists.txt` or `run.cmake`), against the mirrors, and saves no packages. Changes are read with `git`, as the GitHub hook doesn't record them.

## Several plugins in one run

`run.cmake` builds all the plugins in one go and carries on past a failure. The build and install steps report per plugin:

| Plugins that succeeded | Step | Run |
| --- | --- | --- |
| all | `SUCCESS` | pass |
| some | `WARNINGS` | fail; the rest carry on |
| none | `FAILURE` | fail; stops |

The build step reads each plugin's outcome from the summary `run.cmake` prints (`-- FOUNDRY-RESULT: PASS|FAIL ...`, `-- FOUNDRY-SUMMARY: ...`), and sets `built_plugins`. A plugin missing from the summary failed. Each stage hands on only what succeeded, so MTR runs the suites of the plugins that installed. A suite is a `plugin/<x>/<suite>/` directory with `t/*.test` files. A plugin without one is built and installed but not tested, which the suite step's log notes; if no plugin has one, the test steps are skipped. make runs one job per CPU the builder is allotted (`jobs`, 1 for Foundry).

## Configuration

`settings.py` holds the targets (OS × architecture), the MariaDB versions and the targets each builds, and the other settings: the branch Force builds, server sources, dispatcher, and who may Force. To add a target or a MariaDB version, follow the "HOW TO" at the top of `settings.py`. The repository is `FOUNDRY_REPO_URL` in `docker-compose/.env` (MariaDB/foundry) and `.env.dev` (a fork), as for the connectors. The MariaDB version is a build property, so the same builders serve every version. Plugins, changed files, MTR suites and the newest mirrored release are found at run time, so adding a plugin needs no change here.

A version's `targets` must be on the mirrors for that version. A platform that is only on CI so far goes under `ci_only`, which is built only when Force picks a CI `tarbuildnum`. A version not on the mirrors at all, such as a new series, lists its platforms under `ci_only` only; pull requests skip it.

## Saved files

Foundry has its own storage, apart from the server's, as the connectors do: `FOUNDRY_PACKAGES_DIR` on the worker hosts, mounted as `/packages` in Foundry's containers, `/srv/buildbot/foundry` on the master host, served at `<ARTIFACTS_URL>/foundry`:

| What | Where |
| --- | --- |
| Packages, with `sha256sums.txt` | `<version>-<tarbuildnum\|mirror>/<plugin>/<revision>/<builder>/` |
| MTR logs of a failed run | `<version>-<tarbuildnum\|mirror>/<revision>/logs/<builder>/` |
| Foundry archive, with `sha256sums.txt` | `sources/<dispatcher build>/foundry-<commit>.tar.gz` |
| Status report: every plugin's build, install and MTR result per version and platform, failed tests only (the dispatcher's Status link). Versions open on click; it filters by plugin and builder | `runs/<dispatcher build>/status.html`, `status.json` |
| What each package build reports, one file per stage | `runs/<dispatcher build>/<version>/<builder>/` |

Pull requests save no packages, but still publish the archive their builds need.

## Code

| Path | Holds |
| --- | --- |
| `settings.py` | The settings, and the paths and properties the sequences share |
| `builders.py`, `sources.py` | Builders made from the settings; the server source choices |
| `../../sequences/foundry/` | `dispatcher.py`, and `autobake.py` for rpm, deb and bintar |
| `../../../steps/commands/foundry.py` | The commands, and the build step that reads `run.cmake`'s summary |
| `../../../schedulers/foundry.py` | Force, pull request and Triggerable schedulers |

The force and pull request schedulers run on `master-web`, the builders on `master-migration`.
