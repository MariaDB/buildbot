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

podman version
buildah version

# https://github.com/containers/podman/issues/20697
# clean up stale stuff hopefully
#podman system migrate

tarbuildnum=${1}
mariadb_version=${2}
mariadb_version=${mariadb_version#*-}
buildername=${3:-amd64-ubuntu-2004-deb-autobake}
master_branch=${mariadb_version%\.*}
commit=${4:-0}
branch=${5:-${master_branch}}
artifacts_url=${ARTIFACTS_URL:-https://ci.mariadb.org}


# keep in sync with docker-cleanup script
if [[ $branch =~ ^preview ]]; then
  container_tag=${branch#preview-}
else
  container_tag=$master_branch
fi
if [ ! -d "mariadb-docker/$master_branch" ]; then
  master_branch=main
fi
# Container tags must be lower case.
container_tag=${container_tag,,*}
ubi=
arches=( linux/amd64 linux/arm64/v8 linux/ppc64le linux/s390x  )

case "${buildername#*ubuntu-}" in
  2404-deb-autobake)
    pkgver=ubu2404
    ;;
  2204-deb-autobake)
    pkgver=ubu2204
    ;;
  2004-deb-autobake)
    pkgver=ubu2004
    ;;
  *-rhel-9-rpm-autobake)
    ubi=-ubi
    # first arch only
    arches=( linux/amd64 )
    master_branch=${master_branch}-ubi
    ;;
  *)
    echo "unknown base buildername $buildername"
    exit 0
    ;;
esac

image=mariadb-${tarbuildnum}${ubi}

# keep a count of architectures that have reached this step
# and only build once they are all here.

# UBI for the moment only triggers on one arch
reffile="${container_tag}-${tarbuildnum}${ubi}-reference.txt"

# ensure unique entries for each arch
echo "$buildername" >> "$reffile"
sort -u "$reffile" -o "$reffile"

entries=$(wc -l < "$reffile")
if [ "$entries" -lt ${#arches[@]} ]; then
	echo "Only $entries architectures so far"
	# so we're not going to do anything until we have a full list.
	exit 0
fi

# Don't remove file here. Leave a manual retrigger of
# any build of the same tarbuildnum / ubi there to redo
# start the rebuild, without the server rebuild.
# rm "$reffile"

# Annotations - https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
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

#
# BUILD Image
#
builder_noarch=${buildername#*-}

galera_distro=${buildername%-*-autobake}
galera_distro_noarch=${galera_distro#*-}

build() {
  local arch=$1
  declare -a args
  local bbarch=${arch#*/}
  if [ "$bbarch" = arm64/v8 ]; then
    bbarch=aarch64;
  fi
  if [ -n "$ubi" ]
  then
    local repo="mariadb-docker/$master_branch"/MariaDB.repo
    curl "${artifacts_url}/galera/mariadb-4.x-latest-gal-${bbarch}-${galera_distro_noarch}".repo \
      -o "$repo"
    curl "${artifacts_url}/$tarbuildnum/${bbarch}-${builder_noarch}"/MariaDB.repo \
      >> "$repo"
    args=( --build-arg MARIADB_VERSION="$mariadb_version" )
  else
    local galera_repo
    galera_repo="deb [trusted=yes] $(curl "${artifacts_url}/galera/mariadb-4.x-latest-gal-${bbarch}-${galera_distro_noarch}.sources" | sed '/URIs: /!d ; s///;q') ./"
    args=(
      --build-arg REPOSITORY="[trusted=yes] ${artifacts_url}/${tarbuildnum}/${bbarch}-${builder_noarch}/debs ./\n$galera_repo" \
      --build-arg MARIADB_VERSION="1:$mariadb_version+maria~$pkgver" )
  fi
  buildah bud --tag "${image}-${arch}" \
    --layers \
    --platform "$arch" \
    "${args[@]}" \
    "${annotations[@]}" \
   "mariadb-docker/$master_branch"
}

## Because our repos aren't multiarch, or paramitizable by $TARGET_ARCH, we do it separately
##
## intentionally array to simple
## shellcheck disable=SC2124
#archlist="${arches[@]}"
#
## comma separated
#archlist=${archlist// /,}
#buildah bud --manifest "${image}" \
#  --jobs 4 \
#  --layers \
#  --platform "${archlist}" \
#  "${args[@]}" \
#  "${annotations[@]}" \
#  "mariadb-docker/$master_branch"

buildah manifest rm "$image" || echo "already not there"

cleanup()
{
  buildah manifest rm "$image" || echo "already gone"
  for arch in "${arches[@]}"; do
    # -f will remove all tags of same, like wordpress
    buildah rmi -f "${image}-${arch}" || echo "already gone"
  done
  buildah rmi --prune --force
}

trap cleanup ERR

buildah manifest create "$image"

for arch in "${arches[@]}"; do
  build "$arch"
  buildah manifest add "$image" "$image-$arch"
  if [ "$arch" = amd64 ]; then
    buildah tag "${image}-${arch}" "${image}-wordpress"
  fi
done
