# Builder framework

The framework [master-migration](../master-migration/README.md) builds its builders with. A builder is made of reusable sequences of steps, and each step runs a command, usually inside a container started from a [build image](../ci_build_images/README.md).

## Concepts

| Object | Is | Defined in |
| --- | --- | --- |
| `Command` | One command line: compile, configure, run MTR, install packages, ... | `steps/commands/` |
| `ShellStep`, `PropFromShellStep` | A step on the worker that runs a command; the second stores its output in a property | `steps/remote.py` |
| `MasterShellStep` | A step on the master | `steps/master.py` |
| `InContainer(step, docker_environment)` | Runs a `ShellStep` with `docker run`, in the image of a `DockerConfig` | `builders/infra/runtime.py` |
| `BuildSequence` | An ordered list of steps, e.g. "build and test the release packages" | `builders/sequences/` |
| `GenericBuilder` | A named builder made of sequences. `get_config()` gives the Buildbot `BuilderConfig` | `builders/base.py` |

`steps/generators/` build the command lines of CMake and MTR from typed options, so a sequence doesn't write the flags itself. `builders/common.py` holds `docker_config()`, the default container settings, and the release builders shared by several builders.

A builder in master-migration's `master.cfg`:

```python
GenericBuilder(
    name="amd64-openssl3-fips",
    sequences=[
        openssl_fips(jobs=12, config=docker_config(image="rhel9", shm_size="24g"))
    ],
).get_config(workers=DEFAULT_AMD64_WORKER_POOL, tags=["debug"], jobs=12)
```

`jobs` is what the builder takes from the worker's pool of jobs while it runs, and what `make` and MTR get to run in parallel. See [Workers and jobs](../master-migration/README.md#workers-and-jobs).

## Containers

The steps of a build share a Docker volume, mounted on each container's work directory (`/home/buildbot`), so files written there by one step are there for the next. A change outside the volume, such as installed packages, is lost when the container exits, unless the step is wrapped with `container_commit=True`: the container is then committed to the image that the next steps run in.

So a build can change images from one step to the next, and keep the state it needs. The RPM release builder, for instance, builds and installs the packages in the `rhel9` image, commits it, runs MTR on the installed packages, then rebuilds the server from the `.src.rpm` in the clean `rhel9-srpm` image to check that it declares all its build dependencies.

`get_factory()` adds the steps that manage this ([steps/processors.py](steps/processors.py)): pulling and tagging the images, creating the work directories in the volume, committing containers, and removing the containers and volume of the previous and the current run.

A builder can also have a sidecar, a container that runs for the whole build on a network of its own, such as the MariaDB Server that the Connectors' tests connect to. Steps find it through the `SIDECAR_HOST` environment variable.

## Tests

Unit tests are in [test/unit/](test/unit/). Run them with `make test`; they also run in the `unittests` workflow when `configuration/` changes.
