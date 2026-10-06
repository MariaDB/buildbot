# Build images

The images builds run in. Each holds everything needed to build and test the server, the Connectors and the Foundry plugins on one platform, and `buildbot-worker`, which Docker latent workers run. Builders find an image by its tag: `CONTAINER_REGISTRY_URL` (`quay.io/mariadb-foundation/bb-worker:`) followed by the image tag, e.g. `debian12`, with a `dev_` prefix on dev.

An image's Dockerfile is a concatenation of the files here: a base for its distribution family (`debian.Dockerfile`, `fedora.Dockerfile`, `rhel.Dockerfile`, ...), then fragments such as `qpress.Dockerfile` and `buildbot-worker.Dockerfile`. Each family has a GitHub workflow with a matrix of the images it builds (`build-<family>-based.yml`). Their parameters are described in [.github/workflows/README.md](../.github/workflows/README.md).

## Special images

| Images | Built from | Used for |
| --- | --- | --- |
| `<os>-srpm` | `srpm.Dockerfile`, `build-srpm.yml` | Rebuilding the server or a connector from its `.src.rpm`. They are kept close to the bare distribution, to check that the source package declares all its build dependencies. |
| `debian13-msan-clang-22` | `msan.fragment.Dockerfile`, `msan.instrumentedlibs.sh` | Builds with clang and MSAN, ASAN or UBSAN; holds the clang toolchain and libraries built with MSAN |
| `debian11-aocc`, `ubuntu22.04-jepsen-mariadb`, `almalinux8-bintar` | `aocc.Dockerfile`, `jepsen-mariadb.Dockerfile`, `bintar.Dockerfile` | The `-aocc`, Jepsen and `-bintar` builders |

The images install `galera-4` from the Galera packages built by [master-galera](../master-galera/README.md#galera-in-the-servers-build-images), so the server builders can run the Galera suites. Use `nogalera: true` for a platform that has no Galera packages yet.

## From pull request to production

| Event | Result |
| --- | --- |
| Pull request changing a Dockerfile | The images that use it are built, as a check |
| Push to `dev` | They are pushed to quay.io and ghcr.io as `dev_<tag>`, which only dev uses |
| Push to `main` | `dev_<tag>` is copied to `<tag>`, without a rebuild: the image tested on dev goes to production |
| Monthly schedule | Images with `deploy_on_schedule` are rebuilt and go straight to production |

Buildbot pulls only from quay.io. ghcr.io keeps a copy of every image pushed from `dev` as `hist_<tag>_<commit>`, for six months, so a bad image can be rolled back by copying the previous one to the production tag on quay.io:

```sh
skopeo copy --all docker://ghcr.io/mariadb/buildbot/bb-worker:hist_<tag>_<commit> \
  docker://quay.io/mariadb-foundation/bb-worker:<tag>
```

## Reproducing a build

To debug a failure, start the builder's image and repeat its steps, which the build's page lists with their commands:

```sh
docker run -it quay.io/mariadb-foundation/bb-worker:debian12 bash
```

## Building an image locally

Command line examples to build an image locally. Docker and Podman both work; the GitHub workflows use Podman (`podman buildx build`):

```console
# debian
cat debian.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/debian:sid --build-arg MARIADB_BRANCH=11.1 --build-arg BASE_IMAGE=debian:sid
# ubuntu
cat debian.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/ubuntu:22.04 --build-arg MARIADB_BRANCH=11.1 --build-arg BASE_IMAGE=ubuntu:22.04
# fedora
cat fedora.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/fedora:39 --build-arg BASE_IMAGE=fedora:39
# almalinux9
cat centos.Dockerfile pip.Dockerfile common.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/almalinux:9 --build-arg BASE_IMAGE=almalinux:9
# rockylinux9
cat centos.Dockerfile pip.Dockerfile common.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/rockylinux:9 --build-arg BASE_IMAGE=rockylinux:9
# rhel9
cat rhel.Dockerfile qpress.Dockerfile buildbot-worker.Dockerfile >Dockerfile
echo "12345_KEYNAME" >rhel_keyname
echo "12345_ORGID" >rhel_orgid
docker build . -t mariadb.org/buildbot/rhel:9 --build-arg "BASE_IMAGE=ubi9" --secret id=rhel_orgid,src=./rhel_orgid --secret id=rhel_keyname,src=./rhel_keyname
```

## search for missing dependencies

apt:

```bash
for pkg in $(cat list.txt); do echo -e "\n$pkg: $(dpkg -l | grep "$pkg")"; done
```

rpm:

```bash
for pkg in $(cat list.txt); do echo -e "\n$pkg: $(rpm -qa | grep "$pkg")"; done
```

## Best practice

### Sort and remove duplicate packages

One package by line, see:
<https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#sort-multi-line-arguments>

Use the following in vim:

```vim
:sort u
```

### Use hadolint tool to verify the dockerfile

```console
docker run -i -v $(pwd):/mnt -w /mnt hadolint/hadolint:latest hadolint /mnt/fedora.Dockerfile
```
