#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

artifacts_url=${ARTIFACTS_URL:-https://ci.mariadb.org}
typeset -r tarbuildnum="%(prop:tarbuildnum)s"
typeset -r buildername="%(prop:buildername)s"

if [[ $artifacts_url == "https://ci.dev.mariadb.org" ]]; then
  artifact_dest_extra="dev_"
else
  artifact_dest_extra=""
fi

os=$(uname -s)
if [[ $os == "FreeBSD" ]]; then
  typeset artifact_dest="/mnt/autofs/master_${artifact_dest_extra}packages"
else
  typeset artifact_dest="/packages"
fi

[[ -d ./buildbot/logs ]] ||
  err "./buildbot/logs does not exist, no log can be saved"

[[ -d $artifact_dest/$tarbuildnum/logs/$buildername/ ]] ||
  mkdir -p $artifact_dest/$tarbuildnum/logs/$buildername

cp -rv ./buildbot/logs/* "$artifact_dest/$tarbuildnum/logs/$buildername/"

echo "Logs available at $artifacts_url/$tarbuildnum/logs/$buildername/"
