# Workers

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- Builds that ran on the worker on buildbot.dev.mariadb.org, with links. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes
- [ ] `make checkconfig` passes

<!-- Keep the sections below that apply, and delete the others. -->

### Adding a Docker host (Docker latent workers)

- [ ] Its Docker daemon is in `docker_workers` in `master-private.cfg`, on dev and production
- [ ] The master host can reach it
- [ ] Its cap of builds in `worker_locks.yaml`
- [ ] Given to the masters that should use it: `master-variables` / `workers` in `master-private.cfg` for the autogen masters, the `master.cfg` of the others

### Adding a worker to master-migration

- [ ] Entry in `master-migration/workers.yaml`: `name`, `arch`, `total_jobs` (vCPUs), `os_type`
- [ ] Its password in `worker_pass` in `master-private.cfg`, on dev and production
- [ ] A `buildbot-worker` runs on the host for each environment, connected to that environment's master-migration
- [ ] Builders given to it in `master-migration/master.cfg`; the bbm-deploy check's summary shows no worker asked for more jobs than it has

### Adding a worker to master-nonlatent

- [ ] Its password in `worker_pass` in `master-private.cfg`, on dev and production
- [ ] Defined in `master-nonlatent/master.cfg`, with its `max_builds` and `jobs`

### Removing a worker

- [ ] No builder uses it any more
- [ ] Removed from `master-private.cfg` on dev and production, once this is deployed

### Sponsored host

- [ ] Sponsors page updated: `master-web/templates/sponsor.html`, with the logo in `master-web/static/`
