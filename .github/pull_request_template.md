# Pull request

<!--
For a checklist that fits your change, open the Preview tab and follow one
of the links under "Checklists by project": it replaces this text.
-->

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- On buildbot.dev.mariadb.org: which builders ran, with links to their builds. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes
- [ ] `make test` passes, if `configuration/` changed

## Checklists by project

- [Server builders](?expand=1&template=server.md): platforms, versions, builders, install and upgrade tests
- [Galera](?expand=1&template=galera.md)
- [Connectors](?expand=1&template=connectors.md)
- [Foundry](?expand=1&template=foundry.md)
- [Build images](?expand=1&template=build_image.md)
- [Workers](?expand=1&template=worker.md)
