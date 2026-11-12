# Connectors build pipeline

Builds and tests [Connector/C](https://github.com/mariadb-corporation/mariadb-connector-c), [Connector/C++](https://github.com/mariadb-corporation/mariadb-connector-cpp) and [Connector/ODBC](https://github.com/mariadb-corporation/mariadb-connector-odbc), on master-migration.

| Connector | Prefix | Branches | Packages |
| --- | --- | --- | --- |
| C | `cc-` | `3.3`, `3.4` | bintar, Windows MSI |
| C++ | `ccpp-` | `develop`, `master`, `cpp-1.0`, `cpp-1.1` | bintar, deb, rpm, Windows MSI |
| ODBC | `codbc-` | `develop`, `master`, `odbc-3.1`, `odbc-3.2` | bintar, deb, rpm, Windows MSI, macOS |

`bb-*` branches are built too. Pull requests are not.

## Pipeline

1. **Trigger**: a push to a branch above, on the repo in `CONNECTOR_<C|CPP|ODBC>_REPO_URL` ([.env](../../../../docker-compose/.env) for production, [.env.dev](../../../../docker-compose/.env.dev) for dev forks).
1. **Tarball** (`<prefix>tarball-docker`): makes the source package and a `git archive`. For C++ and ODBC, it also reads the C/C series (e.g. `3.4`) of the `libmariadb` submodule into `conc_series`, and fails if it cannot.
1. **Fan out**: the connector's `Triggerable` starts all its builders, passing `tarbuildnum`.
1. **Build and test**, per platform: a bintar; on deb/rpm platforms, also the packages, installed and tested in a clean image. rpm packages are also rebuilt from the `.src.rpm`, and tested on AlmaLinux and Rocky Linux. Linux tests run against a `mariadb:lts` sidecar.

The sanitizer builders (`-msan-clang-22`, `-ubasan-clang-22`) test a bintar and save nothing.

## Which Connector/C (C++ and ODBC)

| Build | Connector/C |
| --- | --- |
| bintar, MSAN, Windows, macOS | The `libmariadb` submodule |
| ASAN/UBSAN | The tip of the submodule's C/C branch (`conc_series`) |
| deb, rpm | `libmariadb-dev` / `MariaDB-devel` from the MariaDB Server repo (on mirror.mariadb.org) the platform lists for `conc_series` |

Deb/rpm platforms, in `concpp.py` and `conodbc.py`, list which MariaDB Server version's repo has each C/C series:

```python
("debian", "13", {"3.4": "11.8"}),  # C/C 3.4 from the server 11.8 repo, no C/C 3.3
```

No server repo listed for the build's C/C series: only the bintar is built, and the deb/rpm steps show as skipped.

## Saved files

Under `CONNECTORS_PACKAGES_DIR/<c|cpp|odbc>` on the worker hosts, served at `<ARTIFACTS_URL>/connector-<c|cpp|odbc>/`:

- `<tarbuildnum>/`: source package, `git archive`, `sha256sums.txt`
- `<tarbuildnum>/<builder>/`: the builder's packages, `sha256sums.txt`

## Maintenance

Test a change on dev by pushing a `bb-*` branch to the fork in `.env.dev`.

### All connectors (C, C++, ODBC)

| When | Do |
| --- | --- |
| Add or remove a platform | Its list in `conc.py`, `concpp.py` or `conodbc.py`. The image `<ops><version>` must exist; for C++/ODBC rpm platforms, also its `-srpm` image |
| Follow a new branch | `C_MAIN_BRANCHES`, `CPP_MAIN_BRANCHES` or `ODBC_MAIN_BRANCHES` in [schedulers/connectors.py](../../../schedulers/connectors.py) |
| Add a special builder | Define it here; add it to its `Triggerable` in `schedulers/connectors.py` and to [master.cfg](../../../../master-migration/master.cfg). Platform builders (`RELEASE_BUILDERS_BY_ARCH`) are added to both automatically |
| Change the workers | `CONNECTORS_WORKERS_BY_ARCH` in master-migration's `master.cfg`; Windows and macOS builders name theirs there |

### C++ and ODBC only: the C/C they use

Change both `concpp.py` and `conodbc.py`.

| When | Do |
| --- | --- |
| A C++/ODBC branch moves to a C/C series already listed (e.g. `odbc-3.1` from 3.3 to 3.4), or a new C++/ODBC series starts | Nothing. Each build reads the C/C series from the branch's `libmariadb` submodule: bintars build that submodule, and deb/rpm install the same series from the server repo the platform lists for it |
| A branch moves to a C/C series not listed yet (e.g. `3.5`) | Add it, with the server version whose repo has it, to each deb/rpm platform where that repo exists. Until then, those platforms build only a bintar |
| A server repo is gone (e.g. 10.11 after EOL) | Remove it from the deb/rpm platforms; else their deb/rpm fail at repo setup |
| Add a deb/rpm platform | Also list which server version's repo has each C/C series |
| C/C changes how it writes its version | Tarball builds fail; update [conc_series.sh](../../../steps/commands/scripts/conc_series.sh) |

Watch for:

- A skipped deb/rpm still gives a green build. Check that a release has its packages.
- deb/rpm use the C/C patch version of the server repo, which can be older than the submodule's.

## Code

| Path | Holds |
| --- | --- |
| `conc.py`, `concpp.py`, `conodbc.py` | The builders and their platforms |
| `../../sequences/connectors/` | The sequences: tarball, bintar, deb, rpm, package tests, Windows, macOS |
| `../../../schedulers/connectors.py` | The change and `Triggerable` schedulers |
| `../../../steps/commands/trigger.py` | The triggers, and the properties they pass on |
| `../../../steps/commands/scripts/conc_series.sh` | Reads the C/C series |
