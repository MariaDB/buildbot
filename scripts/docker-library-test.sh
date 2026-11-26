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


variantfile="${tarbuildnum}-${buildername}-variant.txt"
if [ ! -f "$variantfile" ]; then
  echo "No image was built for $buildername, nothing to test"
  exit 0
fi

image=mariadb-${tarbuildnum}$(<"$variantfile")

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
# The manifest only exists in the run that completed it, whichever
# architecture's autobake that was. Test its amd64 image there, natively;
# other architectures would need emulation.

if [ "$(uname -m)" != x86_64 ]; then
  echo "Not an amd64 worker, no emulated testing"
  exit 2
fi
export DOCKER_LIBRARY_START_TIMEOUT=150

# clean images if test does not succeed
#trap 'buildah rmi "$image"' EXIT

ret=0
mariadb-docker/.test/run.sh --xml=doi.xml "${image}-linux/amd64" || ret=1

if ! curl "$HEALTH_URL" \
    --fail \
    --max-time 5 \
    --retry 3 \
    --retry-max-time 0 \
    --retry-delay 5 \
    --retry-connrefused; then
  echo "Service health check failed. Aborting uploads."
  # A failed test stays a failure, the upload is what's skipped
  if [ "$ret" -ne 0 ]; then
    exit "$ret"
  fi
  exit 2
fi

if [ ! -f doi.xml ]; then
  echo "Test result file doi.xml not created"
  exit 1
fi

curl \
    --fail \
    --max-time 120 \
    --connect-timeout 10 \
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
