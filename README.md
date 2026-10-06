# buildbot.mariadb.org

[![build-centos.pip-based](https://github.com/MariaDB/buildbot/actions/workflows/build-centos.pip-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-centos.pip-based.yml)
[![build-debian-based](https://github.com/MariaDB/buildbot/actions/workflows/build-debian-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-debian-based.yml)
[![build-debian.aocc-based](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.aocc-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.aocc-based.yml)
[![build-debian.jepsen-based](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.jepsen-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.jepsen-based.yml)
[![build-debian.msan-based](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.msan-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-debian.msan-based.yml)
[![build-fedora-based](https://github.com/MariaDB/buildbot/actions/workflows/build-fedora-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-fedora-based.yml)
[![build-opensuse.pip-based](https://github.com/MariaDB/buildbot/actions/workflows/build-opensuse.pip-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-opensuse.pip-based.yml)
[![build-sles.pip-based](https://github.com/MariaDB/buildbot/actions/workflows/build-sles.pip-based.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/build-sles.pip-based.yml)
[![bbw-build-container-rhel](https://github.com/MariaDB/buildbot/actions/workflows/bbw_build_container_rhel.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/bbw_build_container_rhel.yml)
[![bbm-build-container](https://github.com/MariaDB/buildbot/actions/workflows/bbm_build_container.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/bbm_build_container.yml)
[![bbm-deploy](https://github.com/MariaDB/buildbot/actions/workflows/bbm_deploy.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/bbm_deploy.yml)
[![eco container build](https://github.com/MariaDB/buildbot/actions/workflows/eco_containers.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/eco_containers.yml)
[![pre-commit](https://github.com/MariaDB/buildbot/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/MariaDB/buildbot/actions/workflows/pre-commit.yml)

## Overview

This repository is the configuration of the MariaDB Foundation's CI. It runs on a fork of [Buildbot](https://buildbot.net) ([vladbogo/buildbot](https://github.com/vladbogo/buildbot/tree/grid), branch `grid`) and builds and tests:

- [MariaDB Server](https://github.com/MariaDB/server), including the packages that go into a release;
- [Galera](https://github.com/MariaDB/galera) packages;
- the MariaDB Connectors: [C](https://github.com/mariadb-corporation/mariadb-connector-c), [C++](https://github.com/mariadb-corporation/mariadb-connector-cpp) and [ODBC](https://github.com/mariadb-corporation/mariadb-connector-odbc);
- the plugins in [Foundry](https://github.com/MariaDB/foundry).

Two instances run from this repository:

| Environment | Web UI | Deployed from | Saved files | Cross-Reference |
| --- | --- | --- | --- | --- |
| Production | <https://buildbot.mariadb.org> | `main` | <https://ci.mariadb.org> | <https://buildbot.mariadb.org/cr/> |
| Development | <https://buildbot.dev.mariadb.org> | `dev` | <https://ci.dev.mariadb.org> | <https://buildbot.dev.mariadb.org/cr/> |

Cross-Reference records the MTR test failures of the builds, so that a failure can be looked up in earlier runs. Its code is in [MariaDB/cross-reference](https://github.com/MariaDB/cross-reference).

Pull requests target `dev`, and changes reach `main` once they have run on dev. The settings that differ between the two are in [docker-compose/.env](docker-compose/.env) and [docker-compose/.env.dev](docker-compose/.env.dev).

Buildbot runs as several [masters](#masters) that share one database. Each project has an entry point builder that every build of the project starts from ([How changes reach Buildbot](#how-changes-reach-buildbot)). New builders go on [master-migration](master-migration/README.md), which uses the builder framework in [configuration/](configuration/README.md).

## Local development

### Requirements

- [uv](https://github.com/astral-sh/uv), which installs Python 3.9 for the virtual environment;
- `libvirt-dev` and `libmariadb-dev`, to build the Python bindings;
- Docker or Podman, to check the masters' configuration in the masters' images, and for the hadolint hook.

### Setting up

```console
make install
source .venv/bin/activate
make install-pre-commit
```

`make install` creates `.venv`, installs [requirements.txt](requirements.txt), and builds and installs the same Buildbot fork as the masters run, cloned into `.vendor/`. `make clean` removes both, and `make help` lists the other targets. To run the linters on every commit, run `pre-commit install`.

The private settings, `master-private.cfg` and `master-config.yaml`, are links to their `-sample` files, whose placeholder values are enough to load every master. The real ones exist only on the master hosts; see [Secrets](docker-compose/README.md#secrets).

### Checking a change

| Command | Checks |
| --- | --- |
| `make pre-commit-run` | The linters (Python, YAML, shell, Markdown, Dockerfiles, spelling), on the staged files. `make pre-commit-run-all` checks the whole repository. |
| `./validate_master_cfg.sh -e DEV` | `buildbot checkconfig` of every master, in the dev master image with `.env.dev`. It generates the autogen masters first, and prints how many there are per architecture. |
| `./validate_master_cfg.sh -e PROD` | The same, with the production image and `.env` |
| `make checkconfig` | Both of the above |
| `make test` | The unit tests of `configuration/` |

The masters expect the repository at `/srv/buildbot/master` and read their settings from environment variables, which is why `validate_master_cfg.sh` runs them in containers. It also writes `checkconfig_summary.md`, with the jobs master-migration's builders ask of each worker.

### Testing on dev

Merging into `dev` deploys to buildbot.dev.mariadb.org, which builds the maintainers' forks. Read [Testing on dev](docker-compose/README.md#testing-on-dev) before starting builds there.

### Opening a pull request

Open it against `dev`, and link the Jira issue ([MDBF project](https://jira.mariadb.org/projects/MDBF)), as commit messages do with an `MDBF-<number>:` prefix. The [pull request template](.github/pull_request_template.md) links to a checklist for each project: server builders and their install and upgrade VMs, Galera, the Connectors, Foundry, build images and workers.

On a pull request, GitHub runs:

- **pre-commit**, the same linters;
- **bbm-deploy**, the `checkconfig` of every master with the dev and the production images. Its summary shows, for each master-migration worker, the jobs its builders ask for;
- **unittests**, when `configuration/` changes;
- the image builds that use a changed Dockerfile. The image workflows are grouped by family, so only the affected family is rebuilt.

## Masters

The masters share one database and coordinate through a [Crossbar](https://crossbar.io) message router. The builds, and their load, are spread over the masters.

| Master | What it runs |
| --- | --- |
| [master-web](master-web/README.md) | The web UI and the GitHub change hooks. No workers. |
| [master-protected-branches](master-protected-branches/README.md) | `tarball-docker`, the entry point of every server build, and fast server builders that report to GitHub. |
| `autogen/<arch>-master-<n>` | Generated from [os_info.yaml](os_info.yaml): one test builder and one package (`-autobake`) builder per server platform. See [Server builders](docs/server-builders.md). |
| [master-libvirt](master-libvirt/README.md) | Install and upgrade tests of the server packages, in VMs. |
| [master-galera](master-galera/README.md) | Galera packages. |
| [master-nonlatent](master-nonlatent/README.md) | Windows, macOS, FreeBSD and AIX builders, and the Docker Library and WordPress tests. |
| [master-docker-nonstandard, master-docker-nonstandard-2](master-docker-nonstandard/README.md) | Server builders with special configurations: Valgrind, other compilers, full test suites. |
| [master-migration](master-migration/README.md) | The builder framework in [configuration/](configuration/README.md): the Connectors, Foundry, and the server builders moving to it. |

Add new builders to master-migration. The aim is to move the builders of the other masters there over time.

## Workers

Builds run on three kinds of workers:

- **Docker latent** (autogen masters, master-protected-branches, master-galera, master-docker-nonstandard*): for each build, the master starts a container from a [build image](ci_build_images/README.md) on a worker host's Docker daemon. The image contains `buildbot-worker`, which connects back to the master. Each container is a worker of its own, so the master doesn't know which host a build runs on; [worker_locks.yaml](worker_locks.yaml) caps how many builds start on a host.
- **Non-latent** (master-nonlatent, master-migration): a `buildbot-worker` process that runs on the host all the time. On master-migration, each worker has a pool of jobs (its vCPUs) and each build takes as many as its builder asks for, so the host's load is controlled per builder. See [master-migration](master-migration/README.md#workers-and-jobs).
- **libvirt** (master-libvirt): a VM that starts for a build.

## How changes reach Buildbot

GitHub sends push and pull request events to the change hook on master-web. Production receives them from the official repositories; dev receives them from the maintainers' forks, for every project. Each project has its own entry point builder, which every build of that project starts from:

| Project | Entry point | Master | Documentation |
| --- | --- | --- | --- |
| Server | `tarball-docker` | master-protected-branches | [Server builders](docs/server-builders.md) |
| Galera | `trigger-galera-builds` | master-galera | [master-galera](master-galera/README.md) |
| Connectors | `cc-tarball-docker`, `ccpp-tarball-docker`, `codbc-tarball-docker` | master-migration | [Connectors](configuration/builders/definitions/connectors/README.md) |
| Foundry | `foundry-trigger-builders` | master-migration | [Foundry](configuration/builders/definitions/foundry/README.md) |

## Repository layout

| Path | Holds |
| --- | --- |
| `master-*/` | One directory per master, with its `master.cfg` |
| [master.cfg](master.cfg), [os_info.yaml](os_info.yaml), [define_masters.py](define_masters.py) | The template, platform list and generator of the autogen masters |
| [constants.py](constants.py) | Server versions, platforms per version, builders that report to GitHub, extra MTR suites |
| [master_common.py](master_common.py) | The settings all masters share: database, message queue, GitHub status reporting |
| [common_factories.py](common_factories.py), [utils.py](utils.py), [schedulers_definition.py](schedulers_definition.py), [locks.py](locks.py) | The server builders' factories, schedulers and helpers, used by every master except master-migration |
| [configuration/](configuration/README.md) | The builder framework used by master-migration |
| [ci_build_images/](ci_build_images/README.md) | Dockerfiles of the build images |
| [.github/workflows/](.github/workflows/README.md) | Image builds, checks and deployment |
| [docker-compose/](docker-compose/README.md) | The containers that run the masters, and deployment |
| [dashboards/release/](dashboards/release/README.md) | The Server Release Status page |
| `scripts/` | Scripts that builders download from GitHub at build time |
| [minio/](minio/README.md) | The MinIO service used by the S3 tests |
| [Dockerfile](Dockerfile) | The image of the masters |

## Deploying

A push to `dev` deploys dev. An operator deploys production, from `main`. See [Deploying](docker-compose/README.md#deploying).

Some changes reach production as soon as they are merged to `main`, without a deployment:

- scripts that builders download from GitHub when they run: the install and upgrade tests on master-libvirt, the Docker Library tests;
- build images: merging a Dockerfile change to `main` moves the production tags to the images tested on dev. See [Build images](ci_build_images/README.md).

## The master image and the Buildbot upgrade

A Buildbot upgrade is planned, which will rewrite the masters' image, built from [Dockerfile](Dockerfile). Until then, avoid changes to the current Buildbot version and its fork: they would have to be ported to the new version.

## Special Thanks

This project would not have gotten off the ground without the help and support
of Rasmus Johansson. We thank him for his many contributions to the community,
and remember him for his kindness, level headedness, and as an example for us
all.
