#!/usr/bin/env bash

set -xeuvo pipefail

tarbuildnum=${1}
buildername=${2}

builderarch=${buildername%%-*}

image=mariadb-${tarbuildnum}-${builderarch}

#
# TEST Image
#

if [ "${builderarch}" != amd64 ]; then
  export DOCKER_LIBRARY_START_TIMEOUT=350
else
  export DOCKER_LIBRARY_START_TIMEOUT=150
fi

# clean images if test does not succeed
#trap 'buildah rmi "$image"' EXIT

mariadb-docker/.test/run.sh "$image"
trap - EXIT
