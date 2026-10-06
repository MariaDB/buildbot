# Connectors build pipeline

Builds and tests [Connector/C](https://github.com/mariadb-corporation/mariadb-connector-c), [Connector/C++](https://github.com/mariadb-corporation/mariadb-connector-cpp) and [Connector/ODBC](https://github.com/mariadb-corporation/mariadb-connector-odbc), on master-migration.

| Connector | Builder prefix | Branches built | Packages |
| --- | --- | --- | --- |
| C | `cc-` | `3.3`, `3.4` | bintar, Windows MSI |
| C++ | `ccpp-` | `develop`, `master`, `cpp-1.0`, `cpp-1.1` | bintar, deb, rpm, Windows MSI |
| ODBC | `codbc-` | `develop`, `master`, `odbc-3.1`, `odbc-3.2` | bintar, deb, rpm, Windows MSI, macOS |

Every connector also builds `bb-*` branches. Pull requests are not built.

## Pipeline

1. **Trigger**: a push to one of the branches above, on the repository set in `CONNECTOR_C_REPO_URL`, `CONNECTOR_CPP_REPO_URL` or `CONNECTOR_ODBC_REPO_URL` ([.env](../../../../docker-compose/.env) for production, [.env.dev](../../../../docker-compose/.env.dev) for dev's forks).
1. **Tarball** (`<prefix>tarball-docker`): clones the commit, makes the source package and a `git archive`, and saves them under `<ARTIFACTS_URL>/connector-<c|cpp|odbc>/<build number>/`. For C++ and ODBC, it also picks the MariaDB repository whose Connector/C the packages build against (`cpp_to_mariadb_repo`, `odbc_to_mariadb_repo`), from the connector's version.
1. **Fan out**: a `Triggerable` per connector starts all its builders, with the tarball's build number as `tarbuildnum`.
1. **Build and test**, per platform: the bintar, tested in the build image and, for RHEL, in AlmaLinux and Rocky Linux; the deb or rpm packages, installed and tested in a clean image (the upstream distribution image, or the `-srpm` image), and for rpm a rebuild from the `.src.rpm`. On Linux, the tests run against a MariaDB Server (`mariadb:lts`) in a sidecar container.

The sanitizer builders (`-msan-clang-22`, `-ubasan-clang-22`) build and test a bintar without saving it; the ASAN/UBSAN builders build from git, C++ and ODBC with the latest Connector/C of their series.

## Saved files

Under `CONNECTORS_PACKAGES_DIR/<c|cpp|odbc>` on the worker hosts, served at `<ARTIFACTS_URL>/connector-<c|cpp|odbc>/`:

| What | Where |
| --- | --- |
| Source package, `git archive` and `sha256sums.txt` | `<tarbuildnum>/` |
| A builder's packages | `<tarbuildnum>/<builder>/` |

## Maintenance

| To | Change |
| --- | --- |
| Add or remove a platform | The `(ops, version)` lists in `conc.py`, `concpp.py`, `conodbc.py`. The build image `<ops><version>` must exist, and for C++ and ODBC rpm packages its `-srpm` image. |
| Follow a new branch | `C_MAIN_BRANCHES`, `CPP_MAIN_BRANCHES`, `ODBC_MAIN_BRANCHES` in [schedulers/connectors.py](../../../schedulers/connectors.py) |
| Support a new connector series | The MariaDB repository it builds against, in the tarball sequence, and the Connector/C branch the ASAN/UBSAN builders check out, in `../../sequences/connectors/` |
| Add a special builder | Define it here, add it to its connector's `Triggerable` in `schedulers/connectors.py`, and to [master-migration/master.cfg](../../../../master-migration/master.cfg). Platform builders, in `RELEASE_BUILDERS_BY_ARCH`, are added to both automatically. |
| Change the workers | `CONNECTORS_WORKERS_BY_ARCH` in master-migration's `master.cfg`; the Windows and macOS builders name their workers there |

Test a change on dev by pushing to a `bb-*` branch of the fork in `.env.dev`.

## Code

| Path | Holds |
| --- | --- |
| `conc.py`, `concpp.py`, `conodbc.py` | The builders of each connector |
| `../../sequences/connectors/` | Their sequences: tarball, bintar, deb, rpm, package tests, Windows, macOS |
| `../../../schedulers/connectors.py` | The change and `Triggerable` schedulers |
| `../../../steps/commands/trigger.py` | The triggers, and the properties they pass on |
