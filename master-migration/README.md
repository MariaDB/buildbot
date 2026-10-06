# master-migration

The master for builders made with the [builder framework](../configuration/README.md), where new builders go. It runs:

- the [Connectors](../configuration/builders/definitions/connectors/README.md) and [Foundry](../configuration/builders/definitions/foundry/README.md), entirely;
- server builders: the release builders being moved here (`-migration`), the compile-only builders, sanitizers (MSAN, ASAN/UBSAN with clang 22), OpenSSL 3 FIPS, `amd64-ubuntu-2204-bigtest`.

It has only non-latent workers. Most commands run in a Docker container on the worker, started from the same [build images](../ci_build_images/README.md) as the other masters use, so a build can switch images between steps and keep a container's state with `docker commit`. MTR runs as an ordinary shell step, and its results go to the log collector (`MTR_LOG_COLLECTOR_BASE_URL`), so this master doesn't parse the test output.

## Workers and jobs

Workers are listed in [workers.yaml](workers.yaml), their passwords in `worker_pass` in `master-private.cfg`:

```yaml
- name: hz-bbw8
  arch: amd64
  total_jobs: 110      # vCPUs of the host
  os_type: redhat      # debian, redhat, macos, windows, freebsd, aix
  max_builds: 1        # optional
```

Each worker has a pool of `total_jobs` jobs, and each builder asks for `jobs` (`get_config(jobs=...)`). A build starts on a worker only when the worker has that many jobs free, counting the builds running on it ([callables.py](../configuration/builders/callables.py)), so builders that need to finish fast can take more of a host than others. `max_builds` caps the number of builds as well.

The bbm-deploy check prints, per worker, the jobs its builders ask for against its `total_jobs`, flagging a worker whose builders ask for more.

A non-latent worker connects to one master, so this master counts every build it runs on a worker. Dev and production run their own workers on the same hosts, and neither counts the other's builds.

To add a worker: add it to `workers.yaml` and its password to `master-private.cfg` on dev and production, start a `buildbot-worker` on the host for each environment, connecting to this master's port, and give it builders with `WORKER_POOL.get_workers_for_arch(arch=..., names=[...])` in [master.cfg](master.cfg).

## Adding a builder

1. Build it from the sequences in `configuration/builders/sequences/`, or add a sequence there.
1. Add it to `c["builders"]` in [master.cfg](master.cfg), with its workers, tags and `jobs`.
1. Start it. A server builder is started by `tarball-docker` once it is in `SUPPORTED_PLATFORMS` for the versions it should build ([constants.py](../constants.py)). The Connectors and Foundry have their own schedulers, which this master loads instead of the server's.
1. Check it on dev, with the trigger limited to the new builder; see [Testing on dev](../docker-compose/README.md#testing-on-dev).

## Release builders

The `-autobake-migration` builders aim to test the server the way the old Buildbot (buildbot.mariadb.net) did: they build the release packages, install them, and run MTR from the installed tree. The RPM builders also rebuild the server from the `.src.rpm` in a clean `-srpm` image, to check that the source package declares all its build dependencies.

The other masters test differently. The autogen `<arch>-<os>` builders test a RelWithDebInfo build from its build tree, and the `-autobake` builders build the release packages without testing them.

Moving all the release builders here is in progress. Building packages is slow, and with the full test suites on top these builders are too slow to be required checks on GitHub pull requests. Branch protection keeps relying on fast, non-release builders, whose configurations and tests should cover as much of the code as possible.
