# Connectors

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- Builds of a bb-* branch of the dev fork (CONNECTOR_*_REPO_URL in docker-compose/.env.dev), with links. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes

<!-- Keep the sections below that apply, and delete the others. -->

### Adding a platform

- [ ] Added to the `(ops, version)` lists of each connector concerned, in `configuration/builders/definitions/connectors/`
- [ ] Its build image exists, and for C++ and ODBC rpm packages its `-srpm` image
- [ ] Its deb and rpm packages find the Connector/C they need in the MariaDB repository they build against (`*_to_mariadb_repo`)

### Removing a platform

- [ ] Removed from the lists of each connector
- [ ] Its images are removed only if no other builder uses them

### Following a new branch or series

- [ ] Branch in `C_MAIN_BRANCHES`, `CPP_MAIN_BRANCHES` or `ODBC_MAIN_BRANCHES`, in `configuration/schedulers/connectors.py`
- [ ] For a new series: the MariaDB repository its packages build against, and the Connector/C branch the ASAN/UBSAN builders check out
- [ ] Branch links on the home page and the grid view: `master-web/templates/home.jade`, `master-web/templates/grid_view/grid.jade`

### Adding or removing a special builder (sanitizers, Windows, macOS)

- [ ] Defined in the connector's file in `configuration/builders/definitions/connectors/`
- [ ] In the connector's `Triggerable`, in `configuration/schedulers/connectors.py`
- [ ] In `master-migration/master.cfg`, with its workers, tags and `jobs`
