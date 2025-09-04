# Building containerized build environments for Buildbot

**A build environment is a Docker container image used by Buildbot to build and test the server.**

Most of the build environments are created using `build-` workflows that share the same template file: [bbw_build_container_template.yml](bbw_build_container_template.yml).
An exception is [bbw_build_container_rhel.yml](bbw_build_container_rhel.yml), which contains special tasks only applicable to `RHEL`.

Each workflow defines a matrix of images to be built. Adding a new image is as simple as adding a new item to the matrix. See **Adding a new image**.

## From Build to Production

Workflows are triggered by `Dockerfile` changes in [/ci_build_images/](../../ci_build_images/)

In **quay** and **ghcr**, we use two types of tags:

1. `dev_#image_name#` — used by `buildbot.dev.mariadb.org`
1. `#image_name#` — used by `buildbot.mariadb.org`

To update a **production** image, create a Pull Request, merge it into the `DEV` branch, and then sync the changes to `MAIN`.

## Events that trigger a workflow

1. **Pull Request** – The image is built, and the result is reported as a CI Check.
1. **Push to DEV** – The image is built and pushed to **quay** and **ghcr** with the tag `dev_#image_name#`.
1. **Push to MAIN** – The `dev_#image_name#` tag is moved to `#image_name#` in both **quay** and **ghcr**.
1. **Schedule** – See **Workflow dispatcher**.

## Adding a new image

You need to identify the group where the new image belongs.
For example, adding `Fedora 42` means modifying [build-fedora-based.yml](build-fedora-based.yml).

An item should be added under `matrix/include`. For example:

```
  matrix:
    include:
      - image: debian:11
        platforms: linux/amd64, linux/arm64/v8
        branch: 10.11
        nogalera: false
```

**Required parameters**:

- **Image** – This is the value used in the `FROM` instruction of the Dockerfile.
- **Platforms** – Specify more than one to build a multi-architecture container image.
- **Dockerfile** – A space-delimited list of `Dockerfiles` from the **ci_build_images** directory. The order is important, as they are concatenated.

**Optional**:

- **tag** – The displayed tag in **quay** and **ghcr**. If not specified, it's the same as the image name with `:` removed.
- **runner** – GitHub Runner used for the build.
- **clang_version** – Only relevant for [ci_build_images/msan.fragment.Dockerfile](msan.fragment.Dockerfile).
- **branch** – For `debian`-based `Dockerfiles`, this installs build dependencies based on the control file from the specified MariaDB branch, e.g. `mk-build-deps -r -i debian/control`.
- **install_valgrind** – Installs Valgrind in the final container image. Required for builders running tests under Valgrind.
- **files** – JSON list of repository files needed in the final container image.
- **nogalera** – If **True**, `galera-4` will not be installed in the container. Set to **True** when no Galera package is available on `ci.mariadb.org` for the distribution.
- **deploy_on_schedule** – If **True**, the image will be rebuilt and deployed to production on the schedule defined by the **workflow dispatcher**.

## Workflow dispatcher

All `build-` workflows can be manually dispatched using `build-workflow-dispatcher.yml`.

When dispatching the workflow, behavior depends on the `source branch`:

- **DEV** – Builds the image and pushes it to **quay** and **ghcr** with the `dev_#image_name#` tag.
- **MAIN** – Performs a production deployment by moving the `dev_#image_name#` tag to `#image_name#`.

### Scheduler

On the specified schedule, this workflow will trigger (on the default branch) all workflows that implement `is_scheduled_event` as an input to the `workflow_call` event.

```
on:
  schedule:
    - cron: '0 3 3 * *' # Third of the month
```

During this event, the image is not only rebuilt and pushed to **quay** and **ghcr**, but the tag is also moved and deployed to **production**.
