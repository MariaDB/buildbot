# Foundry

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- A Force run on buildbot.dev.mariadb.org, of the fork in FOUNDRY_REPO_URL in docker-compose/.env.dev, with a link to the dispatcher's build. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes
- [ ] `make test` passes (Foundry's tests are `configuration/test/unit/test_foundry_*`)

<!-- Keep the sections below that apply, and delete the others. -->

### Adding a target

- [ ] Follows "HOW TO ADD A TARGET" in `configuration/builders/definitions/foundry/settings.py`, named after the server builder it mirrors
- [ ] Listed under each MariaDB version that should build it, in `targets`, or `ci_only` if that version isn't on the mirrors for it yet
- [ ] Its architecture has workers in `FOUNDRY_WORKERS_BY_ARCH`, in `master-migration/master.cfg`

### Adding a MariaDB version

- [ ] Follows "HOW TO ADD A MARIADB VERSION" in `settings.py`, with the platforms not on the mirrors yet under `ci_only`

### Removing a target or a version

- [ ] Removed from `settings.py`, including from every version that lists the target
