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

[[ -d ./buildbot/logs ]] ||
  err "./buildbot/logs does not exist, no log can be saved"

[[ -d /packages/$tarbuildnum/logs/$buildername/ ]] ||
  mkdir -p /packages/$tarbuildnum/logs/$buildername

cp -rv ./buildbot/logs/* /packages/$tarbuildnum/logs/$buildername/

echo "Logs available at $artifacts_url/$tarbuildnum/logs/$buildername/"
