#!/usr/bin/env bash

set -xeuvo pipefail

# container builds copy permissions and
# depend on go+rx permissions
umask 0002
if [ -d mariadb-docker ]; then
  pushd mariadb-docker
  git fetch
  git checkout origin/next
  popd
else
  git clone --branch next https://github.com/MariaDB/mariadb-docker.git
  pushd mariadb-docker
  git config pull.ff only
  popd
fi

tarbuildnum=${1}
mariadb_version=${2}
mariadb_version=${mariadb_version#*-}
buildername=${3:-amd64-ubuntu-2004-deb-autobake}
master_branch=${mariadb_version%\.*}
commit=${4:-0}
branch=${5:-${master_branch}}

# keep in sync with docker-cleanup script
if [[ $branch =~ ^preview ]]; then
  container_tag=${branch#preview-}
else
  container_tag=$master_branch
fi
# Container tags must be lower case.
container_tag=${container_tag,,*}

case "${buildername#*ubuntu-}" in
  2204-deb-autobake)
    pkgver=ubu2204
    ;;
  2004-deb-autobake)
    pkgver=ubu2004
    ;;
  *)
    echo "unknown base buildername $buildername"
    exit 0
    ;;
esac

builderarch=${buildername%%-*}

declare -a annotations=(
  "--annotation" "org.opencontainers.image.authors=MariaDB Foundation"
  "--annotation" "org.opencontainers.image.documentation=https://hub.docker.com/_/mariadb"
  "--annotation" "org.opencontainers.image.source=https://github.com/MariaDB/mariadb-docker/tree/$(
    cd "mariadb-docker/$master_branch"
    git rev-parse HEAD
  )/$master_branch"
  "--annotation" "org.opencontainers.image.licenses=GPL-2.0"
  "--annotation" "org.opencontainers.image.title=MariaDB Server $container_tag CI build"
  "--annotation" "org.opencontainers.image.description=This is not a Release.\nBuild of the MariaDB Server from CI as of commit $commit"
  "--annotation" "org.opencontainers.image.version=$mariadb_version+$commit"
  "--annotation" "org.opencontainers.image.revision=$commit")

annotate() {
  for item in "${annotations[@]}"; do
    echo " --annotation" \""$item"\"
  done
}

# Annotations - https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
build() {
  image=mariadb-${tarbuildnum}-${builderarch}
  buildah bud --tag "${image}" \
    --layers \
    --arch "$@" \
    --build-arg REPOSITORY="[trusted=yes] https://ci.mariadb.org/$tarbuildnum/${buildername}/debs ./" \
    --build-arg MARIADB_VERSION="1:$mariadb_version+maria~$pkgver" \
    "${annotations[@]}" \
    "mariadb-docker/$master_branch"
}

#
# BUILD Image

if [ "${builderarch}" = aarch64 ]; then
  build arm64 --variant v8
else
  build "${builderarch}"
fi

if [ "${builderarch}" = amd64 ]; then
  podman tag "${image}" "${image}-wordpress"
fi
