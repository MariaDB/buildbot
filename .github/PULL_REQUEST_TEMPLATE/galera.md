# Galera

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- Builds of the dev fork (RazvanLiviuVarzaru/galera) on buildbot.dev.mariadb.org, with links. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes
- [ ] Tested on dev, with a push to the fork
- [ ] The saved files keep their layout, including the `<branch>-latest-<builder>` links; or the server's build images and the release workflows, which read them, change with it
- [ ] Platforms are added and removed in `os_info.yaml`, with the server's checklist
