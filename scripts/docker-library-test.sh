#!/usr/bin/env bash

set -xeuvo pipefail

tarbuildnum=${1}
buildername=${2}

builderarch=${buildername%%-*}

image=mariadb-${tarbuildnum}

if [[ "$buildername" = *-rhel-*-rpm-autobake ]]; then
  image=${image}-ubi
fi

if ! buildah manifest exists "$image"; then
	echo "No manifest we can't test"
	exit 2
fi
#
# TEST Image
#

if [ "${builderarch}" != amd64 ]; then
  export DOCKER_LIBRARY_START_TIMEOUT=350
  echo "Temporarily disable non-amd64 testing"
  exit 2
else
  export DOCKER_LIBRARY_START_TIMEOUT=150
fi

# clean images if test does not succeed
#trap 'buildah rmi "$image"' EXIT

mariadb-docker/.test/run.sh "$image"
trap - EXIT
