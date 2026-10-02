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

Foundry has its own storage, apart from the server's, as the connectors do: `FOUNDRY_PACKAGES_DIR` on the worker hosts, `/srv/buildbot/foundry` on the master host, served at `<ARTIFACTS_URL>/foundry`. A run saves everything under `runs/<dispatcher build>/`, which the dispatcher creates, and that is all of the storage its containers mount, the dispatcher's and its package builds', at the same path under `/packages`. A package build saves to `<version>/<builder>/` there. Their containers don't mount the host's ccache.

| What | Where, under `runs/<dispatcher build>/` |
| --- | --- |
| Foundry archive, with `sha256sums.txt` | `foundry-<commit>.tar.gz` |
| Status report: every plugin's build, install and MTR result per version and platform, failed tests only (the dispatcher's Status link). Versions open on click; it filters by plugin and builder; each builder links to its directory | `status.html`, `status.json` |
| A package build's packages, with `sha256sums.txt` | `<version>/<builder>/plugins/<plugin>/` |
| Its MTR logs, if MTR failed | `<version>/<builder>/logs/` |
| What it reports, one file per stage | `<version>/<builder>/status/` |

Pull requests save no packages, but still publish the archive their builds need.

## Finding a run for a release

A run's directory is named after the dispatcher's build number. To find it from a Foundry commit and a server source, ask the REST API of the master that ran it. For commit `a43c8b2` with 11.4 from CI tarball 74653:

```bash
find_run() {  # <buildbot url> <foundry commit> <version>=<tarbuildnum|mirror>
  curl -fsS "$1/api/v2/builders/foundry-trigger-builders/builds?property=foundry_head&property=foundry_sources&property=branch&order=-number" \
  | jq -r --arg commit "$2" --arg source "$3" '.builds[]
      | select(.properties.foundry_head[0] // "" | startswith($commit))
      | select(.properties.foundry_sources[0] // "" | split(" ") | index($source))
      | select(.properties.branch[0] | startswith("refs/pull/") | not)
      | "\(.number)\t\(["success", "warnings", "failure", "skipped", "exception", "retry", "cancelled"][.results // 7] // "running")"'
}

find_run https://buildbot.mariadb.org a43c8b2 11.4=74653
```

It prints the matching runs, newest first, with each run's result, and leaves out pull requests. The commit can be short; the source is `<version>=<tarbuildnum>` or `<version>=mirror`. The same commit and source forced twice gives two runs. A run's result covers all its plugins, so check `runs/<N>/status.html` for the plugin being released. Its packages for a builder are in `runs/<N>/<version>/<builder>/plugins/<plugin>/`.

## Code

| Path | Holds |
| --- | --- |
| `settings.py` | The settings, and the paths and properties the sequences share |
| `builders.py`, `sources.py` | Builders made from the settings; the server source choices |
| `../../sequences/foundry/` | `dispatcher.py`, and `autobake.py` for rpm, deb and bintar |
| `../../../steps/commands/foundry.py` | The commands, and the build step that reads `run.cmake`'s summary |
| `../../../schedulers/foundry.py` | Force, pull request and Triggerable schedulers |

The force and pull request schedulers run on `master-web`, the builders on `master-migration`.
