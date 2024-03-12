#!/usr/bin/env bash

set -ex

buildername="%(prop:buildername)s"

cd buildbot/build
num_providers_expected=$(find plugin/provider* | wc -l)
if ((num_providers_expected == 0)); then
  echo "No expected providers found, skipping the test"
  exit
fi
if [[ "$buildername" == "kvm-rpm-rhel8-ppc64le" ]]; then
  echo "Test warning"": This builder cannot build all providers due to MDEV-28738"
  num_providers_expected=2
fi

find mkbin/plugin/ -name "provider*.so"
num_providers_built=$(find mkbin/plugin/ -name "provider*.so" | wc -l)

if [[ "$num_providers_built" != "$num_providers_expected" ]]; then
  echo "ERROR: Found $num_providers_built provider libraries, expected $num_providers_expected"
  exit 1
fi
