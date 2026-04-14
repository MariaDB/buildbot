#!/usr/bin/env bash

set -xeuvo pipefail

tarbuildnum=${1}
buildername=${2}
BASE_URL="$3" # e.g., http://100.64.101.1:9990
BRANCH="$4"
REVISION="$5"
PLATFORM="$6"
BBNUM="$7"

UPLOAD_URL="${BASE_URL}/upload-test-results/"
HEALTH_URL="${BASE_URL}/health"


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

ret=0
mariadb-docker/.test/run.sh --xml=doi.xml "$image" || ret=1

if [ $ret ] && ! curl "$HEALTH_URL" \
    --max-time 5 \
    --retry 3 \
    --retry-max-time 0 \
    --retry-delay 5 \
    --retry-connrefused \
    --fail-with-body; then
  echo "Service health check failed. Aborting uploads."
  exit 2
fi

if [ ! -f doi.xml ]; then
  echo "Test result file doi.xml not created"
  exit 1
fi

[ $ret ] && curl \
    --max-time 120 \
    --connect-timeout 10 \
    --fail-with-body \
    -X POST "$UPLOAD_URL" \
    -F "branch=${BRANCH}" \
    -F "revision=${REVISION}" \
    -F "platform=${PLATFORM}" \
    -F "bbnum=${BBNUM}" \
    -F "typ=docker_offical_images" \
    -F "file=@doi.xml;type=application/xml" || exit 1
rm -f doi.xml

trap - EXIT

exit $ret
