#!/usr/bin/env bash

set -ex

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

buildername="%(prop:buildername)s"

cd buildbot/build || err "cd buildbot/build"
# shellcheck disable=SC2010
num_providers_expected=$(ls plugin/* | grep -cE "^provider")
if ((num_providers_expected == 0)); then
  err "No expected providers found, skipping the test"
fi
if [[ $buildername == "kvm-rpm-rhel8-ppc64le" ]]; then
  echo "Test warning: This builder cannot build all providers due to MDEV-28738"
  num_providers_expected=2
fi

find mkbin/plugin/ -name "provider*.so"
num_providers_built=$(find mkbin/plugin/ -name "provider*.so" | wc -l)

if ((num_providers_built != num_providers_expected)); then
  err "found $num_providers_built provider libraries, expected $num_providers_expected"
fi
