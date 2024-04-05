#!/usr/bin/env bash

# This is a template file for a shell script that is used to compile a binary tarball.
# The script CANNOT BE EXECUTED DIRECTLY, it is a template for the buildbot to use.

set -o errexit
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

d=packages
tarbuildnum="%(prop:tarbuildnum)s"
mariadb_version="%(prop:mariadb_version)s"
if [[ -z $ARTIFACTS_URL ]]; then
  artifacts_url="https://ci.mariadb.org"
else
  artifacts_url=$ARTIFACTS_URL
fi

[[ -d packages ]] || mkdir packages
f="${tarbuildnum}${mariadb_version}.tar.gz"

# Do not use flock for AIX/MacOS/FreeBSD
os=$(uname -s)
use_flock=""
if [[ $os != "AIX" && $os != "Darwin" && $os != "FreeBSD" ]]; then
  use_flock="flock $d/$f"
fi
cmd="$use_flock wget -cO $d/$f $artifacts_url/$f"

res=1
for i in {1..10}; do
  if eval "$cmd"; then
    res=0
    break
  else
    sleep "$i"
  fi
done
if ((res != 0)); then
  exit $res
fi

tar -xzf ./packages/$f --strip-components=1
