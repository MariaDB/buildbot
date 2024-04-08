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

typeset -r d="./buildbot"
typeset -r tarbuildnum="%(prop:tarbuildnum)s"
typeset -r buildername="%(prop:buildername)s"

artifacts_url=${ARTIFACTS_URL:-https://ci.mariadb.org}
mtr_test=${TEST_TYPE}

echo "Logs available at $artifacts_url/$tarbuildnum/logs/$buildername"

[[ -d $d/logs/$mtr_test ]] ||
  mkdir -p "$d/logs/$mtr_test"

filename="mysql-test/var/log/mysqld.1.err"
if [[ -f $filename ]]; then
  cp $filename "$d/logs/$mtr_test/mysqld.1.err"
fi

mtr=1
mysqld=1

while true; do
  while true; do
    logname="mysqld.$mysqld.err.$mtr"
    filename="mysql-test/var/$mtr/log/mysqld.$mysqld.err"
    if [ -f $filename ]; then
      cp $filename "$d/logs/$mtr_test/$logname"
    else
      break
    fi
    mysqld=$((mysqld + 1))
  done
  mysqld=1
  mtr=$((mtr + 1))
  filename="mysql-test/var/$mtr/log/mysqld.$mysqld.err"
  if [[ ! -f $filename ]]; then
    break
  fi
done
